// sbldpy module used in test_integration_sbldpy.py, exercising all supported
// types and features.

#include "sbldpy/sbldpy.hh"
#include "PkgA/A.hh"
#include <cstring>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace {
  double add( double a, double b ) { return a + b; }
  std::int64_t iadd( std::int64_t a, std::int64_t b ) { return a + b; }
  std::uint64_t u64max() { return std::numeric_limits<std::uint64_t>::max(); }
  std::int64_t i64min() { return std::numeric_limits<std::int64_t>::min(); }
  std::int8_t i8() { return -5; }
  std::uint16_t u16() { return 65535; }
  int plainint() { return -7; }
  unsigned plainunsigned() { return 7u; }
  float halfvalue() { return 0.5f; }
  bool negate( bool b ) { return !b; }
  void nothing() {}
  std::string greet( const std::string& name ) { return "Hello " + name; }
  std::int64_t clen( const char * s ) { return (std::int64_t)std::strlen(s); }
  std::string strvalue( std::string s ) { return s; }
  double sum( sbldpy::NumpyView<const double> v ) { return std::accumulate( v.begin(), v.end(), 0.0 ); }
  std::int64_t isum( sbldpy::NumpyView<const std::int64_t> v )
  {
    return std::accumulate( v.begin(), v.end(), std::int64_t(0) );
  }
  std::int64_t bsum( sbldpy::NumpyView<const std::uint8_t> v )
  {
    std::int64_t s = 0;
    for ( auto c : v )
      s += c;
    return s;
  }
  //Sum of array of any element type (as double):
  template<class T>
  double tsum( sbldpy::NumpyView<const T> v )
  {
    double s = 0.0;
    for ( auto x : v )
      s += static_cast<double>( x );
    return s;
  }
  //Writable arrays (filled with 0, 1, 2, ...):
  template<class T>
  void tfill( sbldpy::NumpyView<T> v )
  {
    for ( std::size_t i = 0; i < v.size(); ++i )
      v[i] = static_cast<T>( i );
  }
  //Writable array handed over once, and filled in subsequent calls (the Python
  //code keeps the array alive):
  class Filler {
  public:
    void attach( sbldpy::NumpyView<std::int32_t> buf ) { m_buf = buf; }
    std::int64_t fill( std::int64_t n )
    {
      if ( static_cast<std::size_t>( n + 1 ) > m_buf.size() )
        throw std::length_error( "buffer too small" );
      m_buf[0] = static_cast<std::int32_t>( n );
      for ( std::int64_t i = 0; i < n; ++i )
        m_buf[i+1] = static_cast<std::int32_t>( ++m_count );
      return n;
    }
  private:
    sbldpy::NumpyView<std::int32_t> m_buf{ nullptr, 0 };
    std::int32_t m_count = 0;
  };
  sbldpy::NumpyCopy<float> linspace( double a, double b, std::int64_t n )
  {
    std::vector<float> v;
    for ( std::int64_t i = 0; i < n; ++i )
      v.push_back( float( a + (b-a)*double(i)/double(n-1) ) );
    return v;
  }
  sbldpy::NumpyCopy<std::int32_t> ints() { return std::vector<std::int32_t>{ 1, 2, 3 }; }
  sbldpy::NumpyCopy<std::uint8_t> rawbytes() { return std::vector<std::uint8_t>{ 0, 1, 255 }; }
  sbldpy::NumpyCopy<double> empty() { return std::vector<double>{}; }
  std::tuple<std::int64_t,std::string,std::pair<double,bool>> tup( std::array<double,3> a )
  {
    return { 3, "abc", { a[0]+a[1]+a[2], true } };
  }
  std::pair<sbldpy::NumpyCopy<double>,std::int64_t> tuparr()
  {
    return { sbldpy::NumpyCopy<double>( std::vector<double>{ 1.0, 2.0 } ), 2 };
  }
  std::string tupin( std::tuple<std::int64_t,std::string,std::tuple<bool,double>> t )
  {
    return ( std::to_string( std::get<0>(t) ) + std::get<1>(t)
             + ( std::get<0>( std::get<2>(t) ) ? "T" : "F" ) );
  }
  double fail( std::int64_t which )
  {
    if ( which == 0 ) throw std::invalid_argument("bad value");
    if ( which == 1 ) throw std::out_of_range("out of range");
    if ( which == 2 ) throw sbldpy::TypeError("bad type");
    if ( which == 3 ) throw std::overflow_error("overflow");
    if ( which == 4 ) throw std::bad_alloc();
    if ( which == 5 ) throw 17;
    throw std::runtime_error("runtime problem");
  }
  double integrate( sbldpy::Callback<double(double)> f, std::int64_t n )
  {
    double s = 0;
    for ( std::int64_t i = 0; i < n; ++i )
      s += f( ( double(i) + 0.5 ) / double(n) );
    return s / double(n);
  }
  std::string cbstr( sbldpy::Callback<std::string(const std::string&, std::int64_t)> f )
  {
    return f( "x", 3 ) + "!";
  }
  std::string cbargs( sbldpy::Callback<std::string(std::uint64_t,std::int8_t,float,bool,const char*,
                                                   std::pair<std::int32_t,std::string>)> f )
  {
    return f( std::numeric_limits<std::uint64_t>::max(), -3, 0.25f, true, "cstr", { 5, "tuple" } );
  }
  std::int64_t cbvec( sbldpy::Callback<std::vector<double>(sbldpy::NumpyCopy<double>)> f )
  {
    auto v = f( sbldpy::NumpyCopy<double>( std::vector<double>{1,2,3} ) );
    return (std::int64_t)v.size();
  }
  std::int64_t cbbytes( sbldpy::Callback<std::vector<std::uint8_t>()> f )
  {
    std::int64_t s = 0;
    for ( auto c : f() )
      s += c;
    return s;
  }
  std::tuple<std::int64_t,std::string> cbtup( sbldpy::Callback<std::tuple<std::int64_t,std::string>(std::tuple<std::int64_t,double>)> f )
  {
    return f( std::make_tuple( std::int64_t(7), 0.5 ) );
  }
  bool cbbool( sbldpy::Callback<bool(std::int64_t)> f ) { return f( 1 ) && !f( 0 ); }
  std::int64_t cbcatch( sbldpy::Callback<void()> f )
  {
    //Swallows the exception from the callback:
    try {
      f();
    } catch ( sbldpy::CallbackError& ) {
      return 1;
    }
    return 0;
  }
  std::vector<sbldpy::Callback<void()>> g_store;
  void store( sbldpy::Callback<void()> f ) { g_store.push_back( f ); }
  void call_stored() { for ( auto& f : g_store ) f(); }
  void clear_stored() { g_store.clear(); }

  class Counter {
  public:
    Counter( std::int64_t start ) : m_value(start) {}
    std::int64_t increment( std::int64_t n ) { m_value += n; return m_value; }
    std::int64_t value() const { return m_value; }
    void set_value( std::int64_t v ) { m_value = v; }
    sbldpy::NumpyView<const double> history() const { return m_hist; }
    sbldpy::NumpyView<double> history_rw() { return m_hist; }
    void record() { m_hist.push_back( double(m_value) ); }
  private:
    std::int64_t m_value;
    std::vector<double> m_hist;
  };
  Counter make_counter( std::int64_t v ) { return Counter(v*10); }
  std::int64_t counter_value( const Counter& c ) { return c.value(); }
  void counter_bump( Counter& c ) { c.increment(1); }

  std::int64_t g_ninstances = 0;
  struct Tracked {
    Tracked() { ++g_ninstances; }
    Tracked( const Tracked& ) = delete;
    ~Tracked() { --g_ninstances; }
  };

  class NoInit {
  public:
    NoInit( std::int64_t v ) : m_v(v) {}
    std::int64_t value() const { return m_v; }
  private:
    std::int64_t m_v;
  };
  NoInit make_noinit() { return NoInit( 5 ); }
}

SBLDPY_MODULE( feat )
{
  m.doc("Module for testing sbldpy");
  m.def( "add", &add, "Add two numbers", { "a", "b" } );
  m.def( "iadd", &iadd );
  m.def( "u64max", &u64max );
  m.def( "i64min", &i64min );
  m.def( "i8", &i8 );
  m.def( "u16", &u16 );
  m.def( "plainint", &plainint );
  m.def( "plainunsigned", &plainunsigned );
  m.def( "halfvalue", &halfvalue );
  m.def( "negate", &negate );
  m.def( "nothing", &nothing );
  m.def( "greet", &greet, { "name" } );
  m.def( "clen", &clen );
  m.def( "strvalue", &strvalue );
  m.def( "sum", &sum );
  m.def( "isum", &isum );
  m.def( "bsum", &bsum );
  m.def( "sum_f32", &tsum<float> );
  m.def( "sum_i8", &tsum<std::int8_t> );
  m.def( "sum_i16", &tsum<std::int16_t> );
  m.def( "sum_i32", &tsum<std::int32_t> );
  m.def( "sum_u16", &tsum<std::uint16_t> );
  m.def( "sum_u32", &tsum<std::uint32_t> );
  m.def( "sum_u64", &tsum<std::uint64_t> );
  m.def( "fill_f64", &tfill<double> );
  m.def( "fill_f32", &tfill<float> );
  m.def( "fill_i8", &tfill<std::int8_t> );
  m.def( "fill_i32", &tfill<std::int32_t> );
  m.def( "fill_i64", &tfill<std::int64_t> );
  m.def( "fill_u8", &tfill<std::uint8_t> );
  m.def( "fill_u64", &tfill<std::uint64_t> );
  m.add_class<Filler>( "Filler" )
    .def_init<>()
    .def( "attach", &Filler::attach, { "buf" } )
    .def( "fill", &Filler::fill, { "n" } );
  m.def( "linspace", &linspace );
  m.def( "ints", &ints );
  m.def( "rawbytes", &rawbytes );
  m.def( "empty", &empty );
  m.def( "tup", &tup, { "a" } );
  m.def( "tuparr", &tuparr );
  m.def( "tupin", &tupin );
  m.def( "fail", &fail );
  m.def( "integrate", &integrate, { "f", "n" } );
  m.def( "cbstr", &cbstr );
  m.def( "cbargs", &cbargs );
  m.def( "cbvec", &cbvec );
  m.def( "cbbytes", &cbbytes );
  m.def( "cbtup", &cbtup );
  m.def( "cbbool", &cbbool );
  m.def( "cbcatch", &cbcatch );
  m.def( "store", &store );
  m.def( "call_stored", &call_stored );
  m.def( "clear_stored", &clear_stored );
  m.def( "square", []( double x ) { return x*x; } );
  m.def( "a_value", []() { return a_value(); }, "Value from the package library" );
  m.def( "sbldpy_version", []() { return SBLDPY_VERSION; } );
  m.def( "sbldpy_version_str", []() { return std::string(SBLDPY_VERSION_STR); } );
  m.add_class<Counter>( "Counter", "A counter" )
    .def_init<std::int64_t>( { "start" } )
    .def( "increment", &Counter::increment, "Increment", { "n" } )
    .def( "value", &Counter::value )
    .def( "set_value", &Counter::set_value, { "v" } )
    .def( "record", &Counter::record )
    .def( "history", &Counter::history )
    .def( "history_rw", &Counter::history_rw )
    .def( "__repr__", []( const Counter& c ) { return "Counter(" + std::to_string(c.value()) + ")"; } )
    .def_static( "make", &make_counter, { "v" } );
  m.def( "make_counter", &make_counter );
  m.def( "counter_value", &counter_value );
  m.def( "counter_bump", &counter_bump );
  m.add_class<Tracked>( "Tracked" )
    .def_init<>();
  m.def( "ninstances", []() { return g_ninstances; } );
  m.add_class<NoInit>( "NoInit" )
    .def( "value", &NoInit::value );
  m.def( "make_noinit", &make_noinit );
}
