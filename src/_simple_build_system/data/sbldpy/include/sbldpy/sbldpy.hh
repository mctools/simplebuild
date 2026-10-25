#ifndef sbldpy_sbldpy_hh
#define sbldpy_sbldpy_hh

////////////////////////////////////////////////////////////////////////////////
//                                                                            //
// sbldpy: Ultra lightweight Python bindings for C++ code, based on ctypes.   //
//                                                                            //
// This header-only C++17 library is used together with the pure-Python       //
// runtime module "sbldpy". Code using it is NOT compiled with Python headers //
// and NOT linked with libpython. The runtime only uses four plain C          //
// functions of a module (sbldpy_abi_version, sbldpy_module_info,             //
// sbldpy_call and sbldpy_last_error), and exceptions never cross those (or   //
// the callbacks into Python). Only a small set of features is supported on   //
// purpose: more advanced functionality can be implemented in Python code     //
// wrapping the module.                                                       //
//                                                                            //
// Example:                                                                   //
//                                                                            //
//   #include "sbldpy/sbldpy.hh"                                              //
//   double add( double a, double b ) { return a + b; }                       //
//   SBLDPY_MODULE( mymod )                                                   //
//   {                                                                        //
//     m.doc("My module");                                                    //
//     m.def( "add", &add, "Add two numbers", { "a", "b" } );                 //
//   }                                                                        //
//                                                                            //
////////////////////////////////////////////////////////////////////////////////

#define SBLDPY_VERSION_MAJOR 0
#define SBLDPY_VERSION_MINOR 1
#define SBLDPY_VERSION_PATCH 0
#define SBLDPY_VERSION_STR "0.1.0"
//Ever increasing integer (major*1000000+minor*1000+patch):
#define SBLDPY_VERSION 1000
//Version of the binary interface between modules and the Python runtime:
#define SBLDPY_ABI_VERSION 1

#if __cplusplus < 201703L && !( defined(_MSVC_LANG) && _MSVC_LANG >= 201703L )
#  error "sbldpy requires C++17 or later"
#endif

#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <new>
#include <stdexcept>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

//The four functions used by the runtime are explicitly exported, so a module
//library can be compiled with -fvisibility=hidden, keeping its table of
//exported symbols minimal. However, this is only safe if the module code does
//not rely on dynamic_cast or typeid for objects shared with other libraries,
//involving types whose type information is generated in the module itself
//(e.g. templates instantiated in the module, or classes without out-of-line
//virtual functions). With hidden visibility, such type information is private
//to the module, and on some platforms (e.g. macOS) the type comparisons across
//libraries then fail. Compiling with default visibility avoids this.
#if defined(_WIN32)
#  define SBLDPY_EXPORT __declspec(dllexport)
#else
#  define SBLDPY_EXPORT __attribute__((visibility("default")))
#endif

//Functions with static variables holding internal state of a module have hidden
//visibility, so the state is never shared with other modules loaded in the same
//process. With default visibility, such static variables in inline or template
//functions can be unified across all loaded libraries (e.g. as "GNU unique"
//symbols on Linux, even for libraries loaded with RTLD_LOCAL), in which case
//two modules each defining a class with the same name would clash:
#if defined(_WIN32)
#  define SBLDPY_HIDDEN
#else
#  define SBLDPY_HIDDEN __attribute__((visibility("hidden")))
#endif

#define SBLDPY_STRINGIFY( x ) #x
#define SBLDPY_STRINGIFY_VALUE( x ) SBLDPY_STRINGIFY( x )

namespace sbldpy {

  //Exception which can be thrown to raise a TypeError in Python (other
  //exceptions are mapped as follows: std::invalid_argument, std::domain_error
  //and std::length_error -> ValueError, std::out_of_range -> IndexError,
  //std::overflow_error -> OverflowError, std::bad_alloc -> MemoryError, and
  //everything else -> RuntimeError):
  class TypeError : public std::runtime_error {
  public:
    using std::runtime_error::runtime_error;
  };

  //Thrown from Callback::operator() when the Python callback raised an
  //exception. If not caught, the original Python exception is raised (with
  //its traceback) when control returns to Python:
  class CallbackError : public std::runtime_error {
  public:
    CallbackError() : std::runtime_error("exception raised in Python callback") {}
    using std::runtime_error::runtime_error;
  };

  namespace detail {
    template<class T> struct dependent_false : std::false_type {};
    template<class T> using rmcvref_t = std::remove_cv_t<std::remove_reference_t<T>>;

    template<class T>
    constexpr bool is_charlike_v = ( std::is_same_v<T,char> || std::is_same_v<T,wchar_t>
                                     || std::is_same_v<T,char16_t> || std::is_same_v<T,char32_t>
#if defined(__cpp_char8_t)
                                     || std::is_same_v<T,char8_t>
#endif
                                     );

    //Integers which can be returned to Python (any integer up to 64 bits):
    template<class T>
    constexpr bool is_ret_int_v = ( std::is_integral_v<T> && !std::is_same_v<T,bool>
                                    && !is_charlike_v<T> && sizeof(T) <= 8 );
    //Integers which can be received from Python (only 64 bit signed integers,
    //i.e. std::int64_t, to avoid integer width issues):
    template<class T>
    constexpr bool is_param_int_v = is_ret_int_v<T> && std::is_signed_v<T> && sizeof(T) == 8;

    //Element types of numpy arrays:
    template<class T>
    constexpr bool is_dtype_v = ( std::is_same_v<T,double> || std::is_same_v<T,float>
                                  || is_ret_int_v<T> );
    //Element types of arrays received from Python:
    template<class T>
    constexpr bool is_input_dtype_v = ( std::is_same_v<T,double> || is_param_int_v<T>
                                        || std::is_same_v<T,std::uint8_t> );

    template<class T>
    void append_dtype( std::string& out )
    {
      if constexpr ( std::is_same_v<T,double> ) {
        out += "f64";
      } else if constexpr ( std::is_same_v<T,float> ) {
        out += "f32";
      } else {
        out += ( std::is_signed_v<T> ? 'i' : 'u' );
        out += std::to_string( 8 * sizeof(T) );
      }
    }

    //Binary layout of data exchanged with the Python runtime:
    struct StrData { const char * data; std::int64_t size; };
    struct ArrData { const void * data; std::int64_t size; };
    using AssignFct = int(*)( void * dest, const void * data, std::int64_t n );
    struct AssignRes { void * dest; AssignFct assign; };
    using TrampolineFct = int(*)( std::uint64_t token, void ** args, void * result );
    using ReleaseFct = void(*)( std::uint64_t token );

    //Pointers to functions in the Python runtime (one instance per module):
    struct RuntimeCtx {
      std::atomic<TrampolineFct> trampoline{nullptr};
      std::atomic<ReleaseFct> release{nullptr};
      std::atomic<bool> shutdown{false};
    };

    //Each callable passed from Python is identified by a token, which is
    //released when the last C++ copy of the Callback object dies:
    struct CallbackCore {
      std::uint64_t token;
      RuntimeCtx * ctx;
      std::atomic<long> refcount{1};
      void unref()
      {
        if ( refcount.fetch_sub( 1 ) != 1 )
          return;
        if ( !ctx->shutdown.load() ) {
          auto fct = ctx->release.load();
          if ( fct )
            fct( token );
        }
        delete this;
      }
    };
  }

  //Copy of array data, which becomes a new one-dimensional numpy array on the
  //Python side. Must be returned by value:
  template<class T>
  class NumpyCopy {
    static_assert( detail::is_dtype_v<T>,
                   "sbldpy: NumpyCopy<T> requires T to be a fixed width integer type, float or double" );
  public:
    using value_type = T;
    NumpyCopy() = default;
    NumpyCopy( std::vector<T> data ) : m_data(std::move(data)) {}
    const std::vector<T>& data() const noexcept { return m_data; }
    std::vector<T>& data() noexcept { return m_data; }
    std::size_t size() const noexcept { return m_data.size(); }
  private:
    std::vector<T> m_data;
  };

  //One-dimensional view of array data, without copying.
  //
  //As a parameter (only as NumpyView<const double>, NumpyView<const
  //std::int64_t> or NumpyView<const std::uint8_t>), it provides access to
  //data passed from Python (numpy arrays, other objects with the buffer
  //protocol of the correct type, or lists). The data is only valid during
  //the call.
  //
  //As a return value (only from methods of classes), it becomes a numpy
  //array referring directly to the data (read-only if T is const), which
  //keeps the Python object alive. The data must be owned by the C++ object,
  //and the numpy array becomes invalid if the data is reallocated or
  //destroyed (e.g. when a std::vector is resized). Use .copy() on the Python
  //side when in doubt.
  template<class T>
  class NumpyView {
    using value_type_ = std::remove_const_t<T>;
    static_assert( detail::is_dtype_v<value_type_>,
                   "sbldpy: NumpyView<T> requires T to be a (possibly const) fixed width integer type, float or double" );
    using vector_ref = std::conditional_t<std::is_const_v<T>,
                                          const std::vector<value_type_>&,
                                          std::vector<value_type_>&>;
  public:
    using value_type = value_type_;
    static constexpr bool is_readonly = std::is_const_v<T>;
    NumpyView( T * data, std::size_t size ) : m_data(data), m_size(size) {}
    NumpyView( vector_ref v ) : m_data(v.data()), m_size(v.size()) {}
    T * data() const noexcept { return m_data; }
    std::size_t size() const noexcept { return m_size; }
    bool empty() const noexcept { return m_size == 0; }
    T * begin() const noexcept { return m_data; }
    T * end() const noexcept { return m_data + m_size; }
    T& operator[]( std::size_t i ) const noexcept { return m_data[i]; }
  private:
    T * m_data;
    std::size_t m_size;
  };

  //Python callable received as a parameter. It can be copied and stored, and
  //the Python object is kept alive until the last copy dies. Only plain data
  //is passed (copied): Parameters can be integers, floating point numbers,
  //bools, strings, tuples and NumpyCopy objects. Return values can be void,
  //std::int64_t, double, bool, std::string, tuples, std::vector<double>,
  //std::vector<std::int64_t> and std::vector<std::uint8_t>. If the Python
  //callable raises an exception, a sbldpy::CallbackError is thrown.
  template<class Signature> class Callback;

  template<class R, class... Args>
  class Callback<R(Args...)> {
  public:
    using result_type = R;
    explicit Callback( detail::CallbackCore * core ) noexcept : m_core(core) {}
    Callback( const Callback& o ) noexcept : m_core(o.m_core) { m_core->refcount.fetch_add( 1 ); }
    Callback& operator=( const Callback& o ) noexcept
    {
      o.m_core->refcount.fetch_add( 1 );
      m_core->unref();
      m_core = o.m_core;
      return *this;
    }
    ~Callback() { m_core->unref(); }
    R operator()( Args... args ) const;
  private:
    detail::CallbackCore * m_core;
  };

  //Optional documentation string and/or argument names (e.g. { "a", "b" })
  //given when defining functions, methods and constructors:
  struct Extra {
    const char * doc = nullptr;
    std::vector<const char*> argnames;
    bool has_argnames = false;
    Extra() = default;
    Extra( const char * d ) : doc(d) {}
    Extra( std::initializer_list<const char*> a ) : argnames(a), has_argnames(true) {}
  };

  namespace detail {

    ////////////////////////////////////////////////////////////////////////////
    // Type traits                                                            //
    ////////////////////////////////////////////////////////////////////////////

    template<class T> struct is_tuple_like : std::false_type {};
    template<class... T> struct is_tuple_like<std::tuple<T...>> : std::true_type {};
    template<class A, class B> struct is_tuple_like<std::pair<A,B>> : std::true_type {};
    template<class T, std::size_t N> struct is_tuple_like<std::array<T,N>> : std::true_type {};
    template<class T> constexpr bool is_tuple_like_v = is_tuple_like<T>::value;

    template<class T> struct is_numpy_copy : std::false_type {};
    template<class T> struct is_numpy_copy<NumpyCopy<T>> : std::true_type {};
    template<class T> struct is_numpy_view : std::false_type {};
    template<class T> struct is_numpy_view<NumpyView<T>> : std::true_type {};
    template<class T> struct is_callback : std::false_type {};
    template<class S> struct is_callback<Callback<S>> : std::true_type {};
    template<class T> struct is_vector : std::false_type {};
    template<class T, class A> struct is_vector<std::vector<T,A>> : std::true_type {};

    template<class T>
    constexpr bool is_object_v = ( std::is_class_v<T> && !std::is_same_v<T,std::string>
                                   && !std::is_same_v<T,std::string_view>
                                   && !is_tuple_like_v<T> && !is_numpy_copy<T>::value
                                   && !is_numpy_view<T>::value && !is_callback<T>::value
                                   && !is_vector<T>::value );

    //Applies f to each element type of a tuple-like type (passing a null
    //pointer of that type):
    template<class Tup, class F, std::size_t... I>
    constexpr void for_each_type_impl( F&& f, std::index_sequence<I...> )
    {
      ( f( static_cast<std::tuple_element_t<I,Tup>*>(nullptr) ), ... );
    }
    template<class Tup, class F>
    constexpr void for_each_type( F&& f )
    {
      for_each_type_impl<Tup>( std::forward<F>(f), std::make_index_sequence<std::tuple_size_v<Tup>>{} );
    }

    ////////////////////////////////////////////////////////////////////////////
    // Compile time checks of parameter and return types                      //
    ////////////////////////////////////////////////////////////////////////////

    template<class T, bool in_tuple = false>
    constexpr bool check_param()
    {
      using U = rmcvref_t<T>;
      if constexpr ( is_object_v<U> ) {
        static_assert( !in_tuple, "sbldpy: tuples can not contain objects" );
        static_assert( std::is_lvalue_reference_v<T>,
                       "sbldpy: objects can only be passed by reference (T& or const T&)" );
      } else if constexpr ( std::is_pointer_v<U> ) {
        static_assert( std::is_same_v<U,const char*>,
                       "sbldpy: pointers are not supported as parameters (except const char* for strings)" );
        static_assert( !in_tuple, "sbldpy: tuples can contain strings only as std::string" );
      } else {
        static_assert( !std::is_lvalue_reference_v<T> || std::is_const_v<std::remove_reference_t<T>>,
                       "sbldpy: non-const references are only supported for objects of classes" );
        static_assert( !std::is_same_v<U,char>, "sbldpy: char is not supported (use std::int64_t)" );
        static_assert( !std::is_same_v<U,std::string_view>,
                       "sbldpy: std::string_view is not supported (use std::string or const char*)" );
        static_assert( !std::is_enum_v<U>, "sbldpy: enums are not supported (use std::int64_t)" );
        static_assert( !std::is_same_v<U,float>, "sbldpy: float is not supported as parameter type (use double)" );
        static_assert( !std::is_same_v<U,long double>, "sbldpy: long double is not supported (use double)" );
        static_assert( !std::is_integral_v<U> || std::is_same_v<U,bool> || is_param_int_v<U>,
                       "sbldpy: integers can only be received as std::int64_t" );
        static_assert( !is_vector<U>::value,
                       "sbldpy: std::vector is not supported as parameter type (use sbldpy::NumpyView<const T>)" );
        static_assert( !is_numpy_copy<U>::value,
                       "sbldpy: NumpyCopy is not supported as parameter type (use sbldpy::NumpyView<const T>)" );
        if constexpr ( is_numpy_view<U>::value ) {
          static_assert( !in_tuple, "sbldpy: tuples can not contain NumpyView objects" );
          static_assert( U::is_readonly && is_input_dtype_v<typename U::value_type>,
                         "sbldpy: arrays can only be received as NumpyView<const double>,"
                         " NumpyView<const std::int64_t> or NumpyView<const std::uint8_t>" );
        }
        if constexpr ( is_callback<U>::value )
          static_assert( !in_tuple, "sbldpy: tuples can not contain callbacks" );
        if constexpr ( is_tuple_like_v<U> ) {
          static_assert( std::tuple_size_v<U> > 0, "sbldpy: empty tuples are not supported" );
          for_each_type<U>( []( auto * p ) { check_param<std::remove_pointer_t<decltype(p)>,true>(); } );
        }
        static_assert( std::is_arithmetic_v<U> || std::is_same_v<U,std::string> || is_tuple_like_v<U>
                       || is_numpy_view<U>::value || is_callback<U>::value,
                       "sbldpy: unsupported parameter type" );
      }
      return true;
    }

    template<class T, bool is_method = false, bool in_tuple = false>
    constexpr bool check_return()
    {
      static_assert( !std::is_reference_v<T>,
                     "sbldpy: references can not be returned (return by value, or use sbldpy::NumpyView)" );
      static_assert( !std::is_pointer_v<T>,
                     "sbldpy: pointers can not be returned (return by value, or use sbldpy::NumpyView)" );
      using U = std::remove_cv_t<T>;
      if constexpr ( is_object_v<U> ) {
        static_assert( !in_tuple, "sbldpy: tuples can not contain objects" );
      } else if constexpr ( !std::is_void_v<U> ) {
        static_assert( !std::is_same_v<U,char>, "sbldpy: char is not supported as return type" );
        static_assert( !std::is_same_v<U,std::string_view>,
                       "sbldpy: std::string_view is not supported (return std::string)" );
        static_assert( !std::is_enum_v<U>, "sbldpy: enums are not supported as return type" );
        static_assert( !std::is_same_v<U,long double>, "sbldpy: long double is not supported as return type" );
        static_assert( !std::is_integral_v<U> || std::is_same_v<U,bool> || is_ret_int_v<U>,
                       "sbldpy: unsupported integer return type" );
        static_assert( !is_vector<U>::value,
                       "sbldpy: std::vector can not be returned directly (return sbldpy::NumpyCopy"
                       " or sbldpy::NumpyView)" );
        static_assert( !is_callback<U>::value, "sbldpy: callbacks can not be returned" );
        if constexpr ( is_numpy_view<U>::value ) {
          static_assert( !in_tuple, "sbldpy: tuples can not contain NumpyView objects" );
          static_assert( is_method, "sbldpy: NumpyView can only be returned from methods of classes"
                         " (and keeps the Python object alive)" );
        }
        if constexpr ( is_tuple_like_v<U> ) {
          static_assert( std::tuple_size_v<U> > 0, "sbldpy: empty tuples are not supported" );
          for_each_type<U>( []( auto * p ) { check_return<std::remove_pointer_t<decltype(p)>,false,true>(); } );
        }
        static_assert( std::is_arithmetic_v<U> || std::is_same_v<U,std::string> || is_tuple_like_v<U>
                       || is_numpy_view<U>::value || is_numpy_copy<U>::value,
                       "sbldpy: unsupported return type" );
      }
      return true;
    }

    template<class T>
    constexpr bool check_cbarg()
    {
      using U = rmcvref_t<T>;
      static_assert( !std::is_lvalue_reference_v<T> || std::is_const_v<std::remove_reference_t<T>>,
                     "sbldpy: callback parameters can not be non-const references" );
      static_assert( !std::is_same_v<U,char>, "sbldpy: char is not supported in callbacks" );
      static_assert( !std::is_enum_v<U>, "sbldpy: enums are not supported in callbacks" );
      static_assert( !std::is_integral_v<U> || std::is_same_v<U,bool> || is_ret_int_v<U>,
                     "sbldpy: unsupported integer type in callback parameters" );
      if constexpr ( is_tuple_like_v<U> ) {
        static_assert( std::tuple_size_v<U> > 0, "sbldpy: empty tuples are not supported" );
        for_each_type<U>( []( auto * p ) { check_cbarg<std::remove_pointer_t<decltype(p)>>(); } );
      }
      static_assert( ( std::is_arithmetic_v<U> && !std::is_same_v<U,long double> )
                     || std::is_same_v<U,std::string> || std::is_same_v<U,const char*>
                     || is_tuple_like_v<U> || is_numpy_copy<U>::value,
                     "sbldpy: unsupported callback parameter type (only integers, floating point"
                     " numbers, bools, strings, tuples and NumpyCopy objects are supported)" );
      return true;
    }

    template<class T>
    constexpr bool check_cbret()
    {
      static_assert( !std::is_reference_v<T> && !std::is_const_v<T>,
                     "sbldpy: callback return types must be plain values" );
      if constexpr ( !std::is_void_v<T> ) {
        static_assert( !std::is_integral_v<T> || std::is_same_v<T,bool> || is_param_int_v<T>,
                       "sbldpy: integers can only be returned from callbacks as std::int64_t" );
        if constexpr ( is_vector<T>::value )
          static_assert( is_input_dtype_v<typename T::value_type>,
                         "sbldpy: only std::vector<double>, std::vector<std::int64_t> and"
                         " std::vector<std::uint8_t> can be returned from callbacks" );
        if constexpr ( is_tuple_like_v<T> ) {
          static_assert( std::tuple_size_v<T> > 0, "sbldpy: empty tuples are not supported" );
          for_each_type<T>( []( auto * p ) { check_cbret<std::remove_pointer_t<decltype(p)>>(); } );
        }
        static_assert( std::is_same_v<T,double> || std::is_same_v<T,bool> || is_param_int_v<T>
                       || std::is_same_v<T,std::string> || is_vector<T>::value || is_tuple_like_v<T>,
                       "sbldpy: unsupported callback return type (only std::int64_t, double, bool,"
                       " std::string, tuples and std::vector<double|std::int64_t|std::uint8_t>"
                       " are supported)" );
      }
      return true;
    }

    ////////////////////////////////////////////////////////////////////////////
    // Type descriptors (for the Python runtime)                              //
    ////////////////////////////////////////////////////////////////////////////

    //Name of class T in the module (set by add_class):
    template<class T>
    SBLDPY_HIDDEN const char *& class_name()
    {
      static const char * name = nullptr;
      return name;
    }

    inline void append_classref( std::string& out, const char * name )
    {
      if ( !name )
        throw std::logic_error( "a class used as parameter or return type was not added to"
                                " the module with add_class" );
      out += "{\"k\":\"obj\",\"cls\":\"";
      out += name;
      out += "\"}";
    }

    template<class Tup, class F>
    void append_tuple( std::string& out, F appendfct )
    {
      out += "{\"k\":\"tuple\",\"items\":[";
      bool first = true;
      for_each_type<Tup>( [&]( auto * p )
      {
        if ( !first )
          out += ',';
        first = false;
        appendfct( out, p );
      } );
      out += "]}";
    }

    template<class Sig> struct cb_describer;

    template<class T>
    void desc_param( std::string& out )
    {
      using U = rmcvref_t<T>;
      if constexpr ( std::is_same_v<U,bool> ) {
        out += "\"bool\"";
      } else if constexpr ( std::is_integral_v<U> ) {
        out += "\"i64\"";
      } else if constexpr ( std::is_floating_point_v<U> ) {
        out += "\"f64\"";
      } else if constexpr ( std::is_same_v<U,const char*> ) {
        out += "\"cstr\"";
      } else if constexpr ( std::is_same_v<U,std::string> ) {
        out += "\"str\"";
      } else if constexpr ( is_numpy_view<U>::value ) {
        out += "{\"k\":\"arr\",\"dt\":\"";
        append_dtype<typename U::value_type>( out );
        out += "\"}";
      } else if constexpr ( is_tuple_like_v<U> ) {
        append_tuple<U>( out, []( std::string& o, auto * p ) { desc_param<std::remove_pointer_t<decltype(p)>>( o ); } );
      } else if constexpr ( is_callback<U>::value ) {
        cb_describer<U>::describe( out );
      } else {
        append_classref( out, class_name<U>() );
      }
    }

    template<class T>
    void desc_return( std::string& out )
    {
      using U = std::remove_cv_t<T>;
      if constexpr ( std::is_void_v<U> ) {
        out += "\"none\"";
      } else if constexpr ( std::is_same_v<U,bool> ) {
        out += "\"bool\"";
      } else if constexpr ( std::is_integral_v<U> ) {
        out += std::is_signed_v<U> ? "\"int\"" : "\"uint\"";
      } else if constexpr ( std::is_floating_point_v<U> ) {
        out += "\"f64\"";
      } else if constexpr ( std::is_same_v<U,std::string> || std::is_same_v<U,const char*> ) {
        out += "\"str\"";
      } else if constexpr ( is_numpy_copy<U>::value || is_numpy_view<U>::value ) {
        out += is_numpy_copy<U>::value ? "{\"k\":\"copy\",\"dt\":\"" : "{\"k\":\"view\",\"dt\":\"";
        append_dtype<typename U::value_type>( out );
        if constexpr ( is_numpy_view<U>::value )
          out += U::is_readonly ? "\",\"ro\":true}" : "\",\"ro\":false}";
        else
          out += "\"}";
      } else if constexpr ( is_tuple_like_v<U> ) {
        append_tuple<U>( out, []( std::string& o, auto * p ) { desc_return<std::remove_pointer_t<decltype(p)>>( o ); } );
      } else {
        append_classref( out, class_name<U>() );
      }
    }

    template<class T>
    void desc_cbret( std::string& out )
    {
      if constexpr ( std::is_void_v<T> ) {
        out += "\"none\"";
      } else if constexpr ( std::is_same_v<T,bool> ) {
        out += "\"bool\"";
      } else if constexpr ( std::is_integral_v<T> ) {
        out += "\"i64\"";
      } else if constexpr ( std::is_floating_point_v<T> ) {
        out += "\"f64\"";
      } else if constexpr ( std::is_same_v<T,std::string> ) {
        out += "\"str\"";
      } else if constexpr ( is_vector<T>::value ) {
        out += "{\"k\":\"vec\",\"dt\":\"";
        append_dtype<typename T::value_type>( out );
        out += "\"}";
      } else {
        append_tuple<T>( out, []( std::string& o, auto * p ) { desc_cbret<std::remove_pointer_t<decltype(p)>>( o ); } );
      }
    }

    template<class R, class... A>
    struct cb_describer<Callback<R(A...)>> {
      static void describe( std::string& out )
      {
        static_assert( check_cbret<R>() );
        static_assert( ( check_cbarg<A>() && ... && true ) );
        out += "{\"k\":\"cb\",\"args\":[";
        bool first = true;
        //(callback parameters have the same representation as return values):
        ( ( out += ( first ? "" : "," ), desc_return<rmcvref_t<A>>( out ), first = false ), ... );
        (void)first;//(unused for callbacks without parameters)
        out += "],\"ret\":";
        desc_cbret<R>( out );
        out += '}';
      }
    };

    ////////////////////////////////////////////////////////////////////////////
    // Conversion of parameters (Python -> C++)                               //
    ////////////////////////////////////////////////////////////////////////////

    template<class T>
    decltype(auto) get_param( void * p, RuntimeCtx& ctx );

    template<class Tup, std::size_t... I>
    Tup get_tuple( void ** elems, RuntimeCtx& ctx, std::index_sequence<I...> )
    {
      return Tup{ get_param<std::tuple_element_t<I,Tup>>( elems[I], ctx )... };
    }

    template<class T>
    decltype(auto) get_param( void * p, RuntimeCtx& ctx )
    {
      using U = rmcvref_t<T>;
      if constexpr ( std::is_same_v<U,bool> ) {
        return static_cast<bool>( *static_cast<const std::uint8_t*>(p) != 0 );
      } else if constexpr ( std::is_integral_v<U> ) {
        return static_cast<U>( *static_cast<const std::int64_t*>(p) );
      } else if constexpr ( std::is_floating_point_v<U> ) {
        return static_cast<double>( *static_cast<const double*>(p) );
      } else if constexpr ( std::is_same_v<U,const char*> ) {
        return static_cast<const char*>( static_cast<const StrData*>(p)->data );
      } else if constexpr ( std::is_same_v<U,std::string> ) {
        auto s = static_cast<const StrData*>(p);
        return std::string( s->data, static_cast<std::size_t>(s->size) );
      } else if constexpr ( is_numpy_view<U>::value ) {
        auto a = static_cast<const ArrData*>(p);
        return U( static_cast<const typename U::value_type*>(a->data), static_cast<std::size_t>(a->size) );
      } else if constexpr ( is_tuple_like_v<U> ) {
        return get_tuple<U>( static_cast<void**>(p), ctx, std::make_index_sequence<std::tuple_size_v<U>>{} );
      } else if constexpr ( is_callback<U>::value ) {
        return U( new CallbackCore{ *static_cast<const std::uint64_t*>(p), &ctx } );
      } else {
        //Reference to object:
        return *static_cast<U*>( *static_cast<void**>(p) );
      }
    }

    ////////////////////////////////////////////////////////////////////////////
    // Conversion of return values (C++ -> Python)                            //
    ////////////////////////////////////////////////////////////////////////////

    //Strings and arrays referred to by results are kept alive until the next
    //call returning such data on the same thread (the Python runtime copies
    //them immediately):
    struct SlotItem {
      virtual ~SlotItem() = default;
    };
    template<class T>
    struct SlotItemT : SlotItem {
      T value;
      SlotItemT( T&& v ) : value(std::move(v)) {}
    };
    struct ResultSlot {
      std::vector<SlotItem*> items;
      void clear()
      {
        for ( auto e : items )
          delete e;
        items.clear();
      }
      ~ResultSlot() { clear(); }
    };
    SBLDPY_HIDDEN inline ResultSlot& result_slot()
    {
      static thread_local ResultSlot s;
      return s;
    }
    template<class T>
    T& keep_in_slot( T&& v )
    {
      auto& items = result_slot().items;
      items.reserve( items.size() + 1 );
      auto e = new SlotItemT<T>( std::move(v) );
      items.push_back( e );
      return e->value;
    }

    template<class T>
    constexpr bool uses_slot()
    {
      using U = std::remove_cv_t<T>;
      if constexpr ( is_tuple_like_v<U> ) {
        bool res = false;
        for_each_type<U>( [&res]( auto * p ) { res = res || uses_slot<std::remove_pointer_t<decltype(p)>>(); } );
        return res;
      } else {
        return std::is_same_v<U,std::string> || is_numpy_copy<U>::value;
      }
    }

    template<class T, class V>
    void put_value( void * res, V&& v )
    {
      using U = std::remove_cv_t<T>;
      if constexpr ( std::is_same_v<U,bool> ) {
        *static_cast<std::uint8_t*>(res) = ( v ? 1 : 0 );
      } else if constexpr ( std::is_integral_v<U> ) {
        if constexpr ( std::is_signed_v<U> )
          *static_cast<std::int64_t*>(res) = static_cast<std::int64_t>(v);
        else
          *static_cast<std::uint64_t*>(res) = static_cast<std::uint64_t>(v);
      } else if constexpr ( std::is_floating_point_v<U> ) {
        *static_cast<double*>(res) = static_cast<double>(v);
      } else if constexpr ( std::is_same_v<U,std::string> ) {
        auto& s = keep_in_slot( std::string( std::forward<V>(v) ) );
        *static_cast<StrData*>(res) = StrData{ s.data(), static_cast<std::int64_t>(s.size()) };
      } else if constexpr ( is_numpy_copy<U>::value ) {
        auto& a = keep_in_slot( U( std::forward<V>(v) ) );
        *static_cast<ArrData*>(res) = ArrData{ a.data().data(), static_cast<std::int64_t>( a.size() ) };
      } else if constexpr ( is_numpy_view<U>::value ) {
        *static_cast<ArrData*>(res) = ArrData{ v.data(), static_cast<std::int64_t>( v.size() ) };
      } else if constexpr ( is_tuple_like_v<U> ) {
        void ** elems = static_cast<void**>(res);
        std::apply( [elems]( auto&&... e )
        {
          std::size_t i = 0;
          ( put_value<rmcvref_t<decltype(e)>>( elems[i++], std::forward<decltype(e)>(e) ), ... );
        }, std::forward<V>(v) );
      } else {
        static_assert( dependent_false<T>::value, "sbldpy: unexpected return type" );
      }
    }

    //Calls producer() and puts the returned value into the result:
    template<class R, class F>
    void put_result( void * res, F&& producer )
    {
      using U = std::remove_cv_t<R>;
      if constexpr ( std::is_void_v<U> ) {
        producer();
      } else if constexpr ( is_object_v<U> ) {
        //New object owned by Python:
        *static_cast<void**>(res) = static_cast<void*>( new U( producer() ) );
      } else {
        if constexpr ( uses_slot<U>() )
          result_slot().clear();
        put_value<U>( res, producer() );
      }
    }

    ////////////////////////////////////////////////////////////////////////////
    // Callback arguments and return values                                   //
    ////////////////////////////////////////////////////////////////////////////

    //Storage of a callback argument (in the representation of return values):
    template<class T>
    struct CbArg {
      using U = std::decay_t<T>;
      std::conditional_t<std::is_same_v<U,bool>, std::uint8_t,
      std::conditional_t<std::is_integral_v<U>, std::conditional_t<std::is_signed_v<U>,std::int64_t,std::uint64_t>,
      std::conditional_t<std::is_floating_point_v<U>, double,
      std::conditional_t<is_numpy_copy<U>::value, ArrData, StrData>>>> storage;
      void * ptr() { return &storage; }
      explicit CbArg( const U& v )
      {
        if constexpr ( std::is_same_v<U,std::string> ) {
          storage = StrData{ v.data(), static_cast<std::int64_t>( v.size() ) };
        } else if constexpr ( std::is_same_v<U,const char*> ) {
          storage = StrData{ v, static_cast<std::int64_t>( std::char_traits<char>::length( v ) ) };
        } else if constexpr ( is_numpy_copy<U>::value ) {
          storage = ArrData{ v.data().data(), static_cast<std::int64_t>( v.size() ) };
        } else {
          put_value<U>( &storage, v );
        }
      }
    };

    template<class... T>
    struct CbArg<std::tuple<T...>> {
      std::tuple<CbArg<T>...> elems;
      std::array<void*,sizeof...(T)> ptrs;
      template<class V>
      explicit CbArg( const V& v ) : CbArg( v, std::index_sequence_for<T...>{} ) {}
      template<class V, std::size_t... I>
      CbArg( const V& v, std::index_sequence<I...> ) : elems( std::get<I>(v)... )
      {
        std::apply( [this]( auto&... e ) { std::size_t i = 0; ( ( ptrs[i++] = e.ptr() ), ... ); }, elems );
      }
      CbArg( const CbArg& ) = delete;
      void * ptr() { return ptrs.data(); }
    };
    template<class A, class B>
    struct CbArg<std::pair<A,B>> : CbArg<std::tuple<A,B>> {
      using CbArg<std::tuple<A,B>>::CbArg;
    };
    template<class T, std::size_t N>
    struct CbArg<std::array<T,N>> {
      std::vector<CbArg<T>> elems;
      std::array<void*,N> ptrs;
      explicit CbArg( const std::array<T,N>& v )
      {
        elems.reserve( N );
        for ( std::size_t i = 0; i < N; ++i )
          elems.emplace_back( v[i] );
        for ( std::size_t i = 0; i < N; ++i )
          ptrs[i] = elems[i].ptr();
      }
      void * ptr() { return ptrs.data(); }
    };
    template<class T> struct CbArg<const T> : CbArg<T> { using CbArg<T>::CbArg; };
    template<class T> struct CbArg<T&> : CbArg<std::remove_const_t<T>> { using CbArg<std::remove_const_t<T>>::CbArg; };

    template<class V>
    int assign_data( void * dest, const void * data, std::int64_t n ) noexcept
    {
      try {
        using E = typename V::value_type;
        auto d = static_cast<const E*>(data);
        static_cast<V*>(dest)->assign( d, d + n );
        return 0;
      } catch ( ... ) {
        return 1;
      }
    }

    //Storage of a callback return value:
    template<class T>
    struct CbRet {
      T value{};
      std::conditional_t<std::is_same_v<T,bool>, std::uint8_t,
      std::conditional_t<std::is_integral_v<T>, std::int64_t,
      std::conditional_t<std::is_floating_point_v<T>, double, AssignRes>>> storage{};
      CbRet()
      {
        if constexpr ( !std::is_arithmetic_v<T> )
          storage = AssignRes{ &value, &assign_data<T> };
      }
      CbRet( const CbRet& ) = delete;
      void * ptr() { return &storage; }
      T get()
      {
        if constexpr ( std::is_same_v<T,bool> )
          return storage != 0;
        else if constexpr ( std::is_arithmetic_v<T> )
          return static_cast<T>( storage );
        else
          return std::move( value );
      }
    };
    template<>
    struct CbRet<void> {
      void * ptr() { return nullptr; }
      void get() {}
    };
    template<class... T>
    struct CbRet<std::tuple<T...>> {
      std::tuple<CbRet<T>...> elems;
      std::array<void*,sizeof...(T)> ptrs;
      CbRet()
      {
        std::apply( [this]( auto&... e ) { std::size_t i = 0; ( ( ptrs[i++] = e.ptr() ), ... ); }, elems );
      }
      CbRet( const CbRet& ) = delete;
      void * ptr() { return ptrs.data(); }
      std::tuple<T...> get()
      {
        return std::apply( []( auto&... e ) { return std::tuple<T...>( e.get()... ); }, elems );
      }
    };
    template<class A, class B>
    struct CbRet<std::pair<A,B>> {
      CbRet<std::tuple<A,B>> t;
      void * ptr() { return t.ptr(); }
      std::pair<A,B> get() { auto v = t.get(); return { std::move(std::get<0>(v)), std::move(std::get<1>(v)) }; }
    };
    template<class T, std::size_t N>
    struct CbRet<std::array<T,N>> {
      std::array<CbRet<T>,N> elems;
      std::array<void*,N> ptrs;
      CbRet() { for ( std::size_t i = 0; i < N; ++i ) ptrs[i] = elems[i].ptr(); }
      CbRet( const CbRet& ) = delete;
      void * ptr() { return ptrs.data(); }
      std::array<T,N> get()
      {
        std::array<T,N> res;
        for ( std::size_t i = 0; i < N; ++i )
          res[i] = elems[i].get();
        return res;
      }
    };

    template<class R, class... Args, std::size_t... I>
    R invoke_callback( CallbackCore * core, std::index_sequence<I...>, Args&... args )
    {
      auto& ctx = *core->ctx;
      auto tramp = ctx.trampoline.load();
      if ( !tramp || ctx.shutdown.load() )
        throw CallbackError("Python callback invoked after shutdown of the Python runtime");
      std::tuple<CbArg<Args>...> cbargs( args... );
      (void)cbargs;
      std::array<void*,sizeof...(Args)+1> argptrs{ std::get<I>(cbargs).ptr()..., nullptr };
      CbRet<R> res;
      if ( tramp( core->token, argptrs.data(), res.ptr() ) != 0 )
        throw CallbackError();
      return res.get();
    }

  }//detail

  template<class R, class... Args>
  inline R Callback<R(Args...)>::operator()( Args... args ) const
  {
    return detail::invoke_callback<R,Args...>( m_core, std::index_sequence_for<Args...>{}, args... );
  }

  namespace detail {

    ////////////////////////////////////////////////////////////////////////////
    // Signatures of callables                                                //
    ////////////////////////////////////////////////////////////////////////////

    template<class R, class... A>
    struct sig {
      using ret = R;
      using args = std::tuple<A...>;
      static constexpr std::size_t nargs = sizeof...(A);
    };

    template<class F, class = void> struct fn_traits {
      static constexpr bool ok = false;
    };
    template<class R, class... A> struct fn_traits<R(*)(A...)> : sig<R,A...> {
      static constexpr bool ok = true; static constexpr bool is_member = false;
    };
    template<class R, class... A> struct fn_traits<R(*)(A...) noexcept> : fn_traits<R(*)(A...)> {};
    template<class R, class C, class... A> struct fn_traits<R(C::*)(A...)> : sig<R,C&,A...> {
      static constexpr bool ok = true; static constexpr bool is_member = true;
    };
    template<class R, class C, class... A> struct fn_traits<R(C::*)(A...) const> : sig<R,const C&,A...> {
      static constexpr bool ok = true; static constexpr bool is_member = true;
    };
    template<class R, class C, class... A> struct fn_traits<R(C::*)(A...) noexcept> : fn_traits<R(C::*)(A...)> {};
    template<class R, class C, class... A> struct fn_traits<R(C::*)(A...) const noexcept> : fn_traits<R(C::*)(A...) const> {};

    //Lambdas and other functors (signature of operator(), without the object):
    template<class M> struct functor_sig;
    template<class R, class C, class... A> struct functor_sig<R(C::*)(A...)> : sig<R,A...> {};
    template<class R, class C, class... A> struct functor_sig<R(C::*)(A...) const> : sig<R,A...> {};
    template<class R, class C, class... A> struct functor_sig<R(C::*)(A...) noexcept> : sig<R,A...> {};
    template<class R, class C, class... A> struct functor_sig<R(C::*)(A...) const noexcept> : sig<R,A...> {};
    template<class F> struct fn_traits<F,std::void_t<decltype(&F::operator())>>
      : functor_sig<decltype(&F::operator())> {
      static constexpr bool ok = true; static constexpr bool is_member = false;
    };

    template<class F>
    constexpr void check_callable()
    {
      static_assert( fn_traits<F>::ok,
                     "sbldpy: could not deduce the signature of the callable (note that overloaded"
                     " functions must be selected with a cast, and generic lambdas are not supported)" );
    }

    ////////////////////////////////////////////////////////////////////////////
    // Module definition                                                      //
    ////////////////////////////////////////////////////////////////////////////

    //Entries in the table of functions called by sbldpy_call:
    struct Entry {
      void (*invoke)( const void * callable, void ** args, void * result, RuntimeCtx& ctx );
      const void * callable;//never deleted (lives as long as the module)
    };

    struct FuncDef {
      std::string name;
      std::string doc;
      std::vector<const char*> argnames;
      bool has_argnames = false;
      int id = -1;
      void (*describe)( std::string& ) = nullptr;//params and return type
    };

    struct ClassDef {
      std::string name;
      std::string doc;
      int dtor_id = -1;
      bool has_init = false;
      FuncDef init;
      std::vector<FuncDef> methods;
      std::vector<FuncDef> statics;
    };

    struct ModuleData {
      std::string name;
      std::string doc;
      std::vector<Entry> table;
      std::vector<FuncDef> functions;
      std::vector<ClassDef*> classes;//never deleted (lives as long as the module)
      RuntimeCtx rt;
    };

    template<class F, class Self, class... A>
    decltype(auto) call_member( F f, Self& self, A&&... a )
    {
      return ( self.*f )( std::forward<A>(a)... );
    }

    template<class F, class R, class... A, std::size_t... I>
    void call_entry( const void * callable, void ** args, void * res, RuntimeCtx& ctx, std::index_sequence<I...> )
    {
      (void)args; (void)ctx;
      const F& f = *static_cast<const F*>( callable );
      put_result<R>( res, [&]() -> R
      {
        if constexpr ( std::is_member_function_pointer_v<F> )
          return call_member( f, get_param<A>( args[I], ctx )... );
        else
          return f( get_param<A>( args[I], ctx )... );
      } );
    }

    template<class F, class R, class Tup> struct EntryMaker;
    template<class F, class R, class... A>
    struct EntryMaker<F,R,std::tuple<A...>> {
      static void invoke( const void * callable, void ** args, void * res, RuntimeCtx& ctx )
      {
        call_entry<F,R,A...>( callable, args, res, ctx, std::index_sequence_for<A...>{} );
      }
    };

    template<class Tup> struct desc_params;
    template<class... A> struct desc_params<std::tuple<A...>> {
      static void append( std::string& out )
      {
        static_assert( ( check_param<A>() && ... && true ) );
        out += '[';
        bool first = true;
        ( ( out += ( first ? "" : "," ), desc_param<A>( out ), first = false ), ... );
        (void)first;//(unused for functions without parameters)
        out += ']';
      }
    };
    template<class Tup> struct drop_first;
    template<> struct drop_first<std::tuple<>> { using type = std::tuple<>; };
    template<class A0, class... A> struct drop_first<std::tuple<A0,A...>> { using type = std::tuple<A...>; };

    template<bool is_method, class Tr>
    void describe_fct( std::string& out )
    {
      using R = typename Tr::ret;
      static_assert( check_return<R,is_method>() );
      using Args = std::conditional_t<is_method,typename drop_first<typename Tr::args>::type,typename Tr::args>;
      out += "\"params\":";
      desc_params<Args>::append( out );
      out += ",\"ret\":";
      desc_return<R>( out );
    }

    inline void apply_extras( FuncDef& fd, std::size_t nparams, const Extra& e1, const Extra& e2 )
    {
      for ( auto e : { &e1, &e2 } ) {
        if ( e->doc ) {
          if ( !fd.doc.empty() )
            throw std::logic_error( "documentation given twice for " + fd.name );
          fd.doc = e->doc;
        }
        if ( e->has_argnames ) {
          if ( fd.has_argnames )
            throw std::logic_error( "argument names given twice for " + fd.name );
          fd.has_argnames = true;
          fd.argnames = e->argnames;
        }
      }
      if ( fd.has_argnames && fd.argnames.size() != nparams )
        throw std::logic_error( "wrong number of argument names given for " + fd.name
                                + " (expected " + std::to_string( nparams ) + ")" );
    }

    template<class Tr, bool is_method, class F>
    FuncDef make_funcdef( ModuleData& d, const char * name, F&& f, const Extra& e1, const Extra& e2 )
    {
      using FD = std::decay_t<F>;
      FuncDef fd;
      fd.name = name;
      apply_extras( fd, Tr::nargs - ( is_method ? 1 : 0 ), e1, e2 );
      fd.describe = &describe_fct<is_method,Tr>;
      d.table.push_back( Entry{ &EntryMaker<FD,typename Tr::ret,typename Tr::args>::invoke,
                                new FD( std::forward<F>(f) ) } );
      fd.id = static_cast<int>( d.table.size() - 1 );
      return fd;
    }

  }//detail

  template<class T> class Class;

  class Module {
  public:
    explicit Module( detail::ModuleData& d ) : m_d(d) {}

    Module& doc( const char * d ) { m_d.doc = d; return *this; }

    //Define function (function pointer or lambda with supported parameter and
    //return types), optionally followed by a doc string and/or argument names
    //(e.g. { "a", "b" }):
    template<class F>
    Module& def( const char * name, F&& f, const Extra& e1 = Extra(), const Extra& e2 = Extra() )
    {
      using FD = std::decay_t<F>;
      detail::check_callable<FD>();
      using Tr = detail::fn_traits<FD>;
      static_assert( !Tr::is_member, "sbldpy: member functions must be defined on classes" );
      m_d.functions.push_back( detail::make_funcdef<Tr,false>( m_d, name, std::forward<F>(f), e1, e2 ) );
      return *this;
    }

    //Add class (objects are owned by Python):
    template<class T>
    Class<T> add_class( const char * name, const char * doc = nullptr );

  private:
    detail::ModuleData& m_d;
  };

  template<class T>
  class Class {
    static_assert( detail::is_object_v<T>, "sbldpy: unsupported class type" );
  public:
    Class( detail::ModuleData& m, detail::ClassDef& d ) : m_m(m), m_d(d) {}

    //Constructor, calling T(A...) (at most one per class):
    template<class... A>
    Class& def_init( const Extra& e1 = Extra(), const Extra& e2 = Extra() )
    {
      if ( m_d.has_init )
        throw std::logic_error( "only one constructor can be defined for class " + m_d.name );
      auto f = []( A... a ) { return T( static_cast<A>(a)... ); };
      m_d.init = detail::make_funcdef<detail::sig<T,A...>,false>( m_m, "__init__", f, e1, e2 );
      m_d.has_init = true;
      return *this;
    }

    //Method (member function pointer of T, or function/lambda taking T& or
    //const T& as first parameter):
    template<class F>
    Class& def( const char * name, F&& f, const Extra& e1 = Extra(), const Extra& e2 = Extra() )
    {
      using FD = std::decay_t<F>;
      detail::check_callable<FD>();
      using Tr = detail::fn_traits<FD>;
      static_assert( Tr::nargs >= 1, "sbldpy: methods must take the object as first parameter" );
      using Self = std::tuple_element_t<0,typename Tr::args>;
      static_assert( std::is_lvalue_reference_v<Self> && std::is_same_v<detail::rmcvref_t<Self>,T>,
                     "sbldpy: methods must be member functions of the class itself, or take the object"
                     " as first parameter (as T& or const T&)" );
      m_d.methods.push_back( detail::make_funcdef<Tr,true>( m_m, name, std::forward<F>(f), e1, e2 ) );
      return *this;
    }

    //Static method:
    template<class F>
    Class& def_static( const char * name, F&& f, const Extra& e1 = Extra(), const Extra& e2 = Extra() )
    {
      using FD = std::decay_t<F>;
      detail::check_callable<FD>();
      using Tr = detail::fn_traits<FD>;
      static_assert( !Tr::is_member, "sbldpy: static methods can not be member functions" );
      m_d.statics.push_back( detail::make_funcdef<Tr,false>( m_m, name, std::forward<F>(f), e1, e2 ) );
      return *this;
    }

  private:
    detail::ModuleData& m_m;
    detail::ClassDef& m_d;
  };

  namespace detail {
    template<class T>
    void destroy_object( const void *, void ** args, void *, RuntimeCtx& )
    {
      delete static_cast<T*>( *static_cast<void**>( args[0] ) );
    }
  }

  template<class T>
  inline Class<T> Module::add_class( const char * name, const char * doc )
  {
    if ( detail::class_name<T>() )
      throw std::logic_error( std::string("class added twice: ") + name );
    detail::class_name<T>() = name;
    auto cd = new detail::ClassDef;
    m_d.classes.push_back( cd );
    cd->name = name;
    cd->doc = doc ? doc : "";
    m_d.table.push_back( detail::Entry{ &detail::destroy_object<T>, nullptr } );
    cd->dtor_id = static_cast<int>( m_d.table.size() - 1 );
    return Class<T>( m_d, *cd );
  }

  namespace detail {

    ////////////////////////////////////////////////////////////////////////////
    // Module information and the exported functions                          //
    ////////////////////////////////////////////////////////////////////////////

    inline void append_json_str( std::string& out, const std::string& s )
    {
      out += '"';
      for ( char c : s ) {
        if ( c == '"' || c == '\\' ) {
          out += '\\';
          out += c;
        } else if ( static_cast<unsigned char>(c) < 0x20 ) {
          char buf[8];
          std::snprintf( buf, sizeof(buf), "\\u%04x", static_cast<unsigned>(c) );
          out += buf;
        } else {
          out += c;
        }
      }
      out += '"';
    }

    inline void append_json_func( std::string& out, const FuncDef& fd )
    {
      out += "{\"name\":";
      append_json_str( out, fd.name );
      out += ",\"id\":" + std::to_string( fd.id ) + ",\"doc\":";
      append_json_str( out, fd.doc );
      if ( fd.has_argnames ) {
        out += ",\"argnames\":[";
        for ( std::size_t i = 0; i < fd.argnames.size(); ++i ) {
          if ( i )
            out += ',';
          append_json_str( out, fd.argnames[i] );
        }
        out += ']';
      }
      out += ',';
      fd.describe( out );
      out += '}';
    }

    inline void append_json_funcs( std::string& out, const std::vector<FuncDef>& v )
    {
      out += '[';
      for ( std::size_t i = 0; i < v.size(); ++i ) {
        if ( i )
          out += ',';
        append_json_func( out, v[i] );
      }
      out += ']';
    }

    inline void hidden_init_runtime( const void *, void ** args, void *, RuntimeCtx& ctx )
    {
      ctx.trampoline.store( reinterpret_cast<TrampolineFct>( *static_cast<void**>( args[0] ) ) );
      ctx.release.store( reinterpret_cast<ReleaseFct>( *static_cast<void**>( args[1] ) ) );
      ctx.shutdown.store( false );
    }

    inline void hidden_shutdown( const void *, void **, void *, RuntimeCtx& ctx )
    {
      ctx.shutdown.store( true );
    }

    struct ModuleState {
      ModuleData data;
      std::string info;
      std::string init_error;
      ModuleState( const char * name, void(*deffct)(Module&) )
      {
        try {
          data.name = name;
          Module m( data );
          deffct( m );
          data.table.push_back( Entry{ &hidden_init_runtime, nullptr } );
          data.table.push_back( Entry{ &hidden_shutdown, nullptr } );
          const std::size_t ntable = data.table.size();
          std::string& out = info;
          out += ( "{\"sbldpy_version\":" SBLDPY_STRINGIFY_VALUE(SBLDPY_VERSION)
                   ",\"sbldpy_version_str\":\"" SBLDPY_VERSION_STR "\""
                   ",\"abi_version\":" SBLDPY_STRINGIFY_VALUE(SBLDPY_ABI_VERSION) ",\"module\":" );
          append_json_str( out, data.name );
          out += ",\"doc\":";
          append_json_str( out, data.doc );
          out += ",\"functions\":";
          append_json_funcs( out, data.functions );
          out += ",\"classes\":[";
          for ( std::size_t i = 0; i < data.classes.size(); ++i ) {
            const ClassDef& c = *data.classes[i];
            out += ( i ? ",{\"name\":" : "{\"name\":" );
            append_json_str( out, c.name );
            out += ",\"doc\":";
            append_json_str( out, c.doc );
            out += ",\"dtor\":" + std::to_string( c.dtor_id ) + ",\"init\":";
            if ( c.has_init )
              append_json_func( out, c.init );
            else
              out += "null";
            out += ",\"methods\":";
            append_json_funcs( out, c.methods );
            out += ",\"staticmethods\":";
            append_json_funcs( out, c.statics );
            out += '}';
          }
          out += "],\"hidden\":{\"init_runtime\":" + std::to_string( ntable - 2 )
            + ",\"shutdown\":" + std::to_string( ntable - 1 ) + "}}";
        } catch ( std::exception& e ) {
          init_error = std::string("Error in definition of sbldpy module ") + name + ": " + e.what();
        } catch ( ... ) {
          init_error = std::string("Unknown error in definition of sbldpy module ") + name;
        }
      }
    };

    //Error message of the last failed call on this thread:
    SBLDPY_HIDDEN inline std::string& last_error()
    {
      static thread_local std::string s;
      return s;
    }

    inline const char * module_info( ModuleState& s ) noexcept
    {
      if ( !s.init_error.empty() ) {
        last_error() = s.init_error;
        return nullptr;
      }
      return s.info.c_str();
    }

    //Error codes returned by sbldpy_call:
    enum ErrorCode : int { EC_OK = 0, EC_RUNTIME = 1, EC_VALUE = 2, EC_INDEX = 3, EC_TYPE = 4,
                           EC_OVERFLOW = 5, EC_MEMORY = 6, EC_CALLBACK = 7 };

    inline int set_error( int ec, const char * msg ) noexcept
    {
      try {
        last_error() = msg;
      } catch ( ... ) {
      }
      return ec;
    }

    inline int module_call( ModuleState& s, int id, void ** args, void * result ) noexcept
    {
      try {
        if ( !s.init_error.empty() )
          throw std::runtime_error( s.init_error );
        if ( id < 0 || static_cast<std::size_t>(id) >= s.data.table.size() )
          throw std::runtime_error( "sbldpy: invalid function id" );
        const Entry& e = s.data.table[static_cast<std::size_t>(id)];
        e.invoke( e.callable, args, result, s.data.rt );
        return EC_OK;
      } catch ( CallbackError& e ) {
        return set_error( EC_CALLBACK, e.what() );
      } catch ( TypeError& e ) {
        return set_error( EC_TYPE, e.what() );
      } catch ( std::invalid_argument& e ) {
        return set_error( EC_VALUE, e.what() );
      } catch ( std::domain_error& e ) {
        return set_error( EC_VALUE, e.what() );
      } catch ( std::length_error& e ) {
        return set_error( EC_VALUE, e.what() );
      } catch ( std::out_of_range& e ) {
        return set_error( EC_INDEX, e.what() );
      } catch ( std::overflow_error& e ) {
        return set_error( EC_OVERFLOW, e.what() );
      } catch ( std::bad_alloc& ) {
        return set_error( EC_MEMORY, "" );
      } catch ( std::exception& e ) {
        return set_error( EC_RUNTIME, e.what() );
      } catch ( ... ) {
        return set_error( EC_RUNTIME, "unknown C++ exception" );
      }
    }

    constexpr bool streq( const char * a, const char * b )
    {
      return *a == *b && ( *a == '\0' || streq( a + 1, b + 1 ) );
    }

  }//detail

}//sbldpy

//If the build system defines SBLDPY_MODNAME (e.g. -DSBLDPY_MODNAME=mymod), the
//name given to SBLDPY_MODULE(..) must match it:
#ifdef SBLDPY_MODNAME
#  define SBLDPY_CHECK_MODNAME( modname )                                     \
  static_assert( ::sbldpy::detail::streq( #modname, SBLDPY_STRINGIFY_VALUE(SBLDPY_MODNAME) ), \
                 "sbldpy: name in SBLDPY_MODULE(..) must match the name of the module" );
#else
#  define SBLDPY_CHECK_MODNAME( modname )
#endif

//Defines the module. Must be used exactly once per module, followed by a
//block of code defining the contents of the module (available as "m"). The
//block becomes the body of a member function, with "m" being a data member, so
//that it does not shadow global variables named "m" (as would a function
//parameter, triggering -Wshadow warnings):
#define SBLDPY_MODULE( modname )                                              \
  SBLDPY_CHECK_MODNAME( modname )                                             \
  namespace {                                                                 \
    struct SbldpyModuleDefiner {                                              \
      ::sbldpy::Module& m;                                                    \
      void define();                                                          \
    };                                                                        \
  }                                                                           \
  static void sbldpy_define_module_impl( ::sbldpy::Module& sbldpy_module )    \
  {                                                                           \
    SbldpyModuleDefiner{ sbldpy_module }.define();                            \
  }                                                                           \
  static ::sbldpy::detail::ModuleState& sbldpy_module_state()                 \
  {                                                                           \
    static ::sbldpy::detail::ModuleState sbldpy_state( #modname, &sbldpy_define_module_impl ); \
    return sbldpy_state;                                                      \
  }                                                                           \
  extern "C" SBLDPY_EXPORT int sbldpy_abi_version()                           \
  {                                                                           \
    return SBLDPY_ABI_VERSION;                                                \
  }                                                                           \
  extern "C" SBLDPY_EXPORT const char * sbldpy_module_info()                  \
  {                                                                           \
    return ::sbldpy::detail::module_info( sbldpy_module_state() );            \
  }                                                                           \
  extern "C" SBLDPY_EXPORT int sbldpy_call( int id, void ** args, void * result ) \
  {                                                                           \
    return ::sbldpy::detail::module_call( sbldpy_module_state(), id, args, result ); \
  }                                                                           \
  extern "C" SBLDPY_EXPORT const char * sbldpy_last_error()                   \
  {                                                                           \
    return ::sbldpy::detail::last_error().c_str();                            \
  }                                                                           \
  void SbldpyModuleDefiner::define()

#endif
