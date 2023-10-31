#ifndef Core_Python_hh
#define Core_Python_hh

//---------------------------------------------------------------------------

// This header file provides pybind11 functionality in a py:: namespace along
// with a PYTHON_MODULE macro to be used in the pycpp_XXX compiled python
// modules of the packages. It includes the necessary hacks and workarounds to
// work on the various platforms (try not to put any hacks/workarounds
// elsewhere!).

//---------------------------------------------------------------------------

// We need the same macros here as in Types.hh since pybind headers might include
// the same files and thus spoil Types.hh:

#ifndef __STDC_LIMIT_MACROS
#  define __STDC_LIMIT_MACROS
#endif
#ifndef __STDC_CONSTANT_MACROS
#  define __STDC_CONSTANT_MACROS
#endif
#ifndef __STDC_FORMAT_MACROS
#  define __STDC_FORMAT_MACROS
#endif

#ifdef sbld_xstringify
#  undefine sbld_xstringify
#endif
#ifdef sbld_stringify
#  undefine sbld_stringify
#endif
#define sbld_xstringify(s) #s
#define sbld_stringify(s) sbld_xstringify(s)

#include <pybind11/pybind11.h>
namespace py = pybind11;

namespace pyextra {

  //If using python modules from inside regular (libsrc/* or app_*/*) non-python
  //C++ code, one must ensure python has been initialised.
  inline bool isPyInit() { return Py_IsInitialized(); }

  void pyInit( const char * argv0 = nullptr );//only provide sys.argv[0] (defaulting to "dummyargv0")
  void pyInit( int argc, char** argv );//Transfer C++ cmdline to sys.argv

  inline void ensurePyInit()
  {
    if (!Py_IsInitialized())
      pyInit();
  }

  inline py::object pyimport( const char * name ) { return py::module_::import(name); }
}

#ifdef PYDEF
#  undefine PYDEF
#endif
#ifdef PYMOD
#  undefine PYMOD
#endif

//TODO: Revist these here post-migration:
#define PYTHON_MODULE PYBIND11_MODULE(PYMODNAME, m)
#define PYTHON_MODULE2 PYBIND11_MODULE(PYMODNAME, themod)
#define PYTHON_MODULE3 PYBIND11_MODULE(PYMODNAME, mod)
#define PYDEF m.def
#define PYMOD m,
#define PYDEF2 themod.def
#define PYMOD2 themod,
#define PYBOOSTNONCOPYABLE
#define PYBOOSTNOINIT
#define PYADDPROPERTY def_property
#define PYADDREADONLYPROPERTY def_property_readonly

namespace pybind11 {

  //Adding this for migration purposes: (fixme remote)
  constexpr return_value_policy return_ptr() noexcept { return return_value_policy::reference; }

  //Adding this for migration purposes (fixme):
  template <class T>
  inline T extract( py::object o )
  {
    return o.cast<T>();
  }

}

#endif
