#ifndef Core_Python_hh
#define Core_Python_hh

//---------------------------------------------------------------------------

// This header file provides pybind11 functionality in a py:: namespace along
// with a PYTHON_MODULE macro to be used in the pycpp_XXX compiled python
// modules of the packages. It includes the necessary hacks and workarounds to
// work on the various platforms (try not to put any hacks/workarounds
// elsewhere!). It should only be used from C++ code in pycpp_*/ or app_*/
// folders, since the code in libsrc/ folders is not linked with python and
// pybind.

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

#include <pybind11/pybind11.h>

//Convenience alias of pybind11 namespace:
namespace py = pybind11;

//A few extra convenience functions in the pyextra namespace:
namespace pyextra {

  //If using python modules from inside regular (libsrc/* or app_*/*) non-python
  //C++ code, one must ensure python has been initialised (although for app_*/*
  //code, one is most likely better off using a pybind11 scoped_interpreter).
  inline bool isPyInit() { return Py_IsInitialized(); }
  inline void ensurePyInit()
  {
    if (!Py_IsInitialized())
      Py_Initialize();
  }
  //Importing modules (same as py::module_::import):
  inline py::object pyimport( const char * name ) { return py::module_::import(name); }
}

//Convenience macro for defining a python module:
#ifdef PYTHON_MODULE
#  undef PYTHON_MODULE
#endif
#define PYTHON_MODULE( modvarname ) PYBIND11_MODULE(PYMODNAME, modvarname)

//Convenience macros for stringification:
#ifdef sbld_xstringify
#  undef sbld_xstringify
#endif
#ifdef sbld_stringify
#  undef sbld_stringify
#endif
#define sbld_xstringify(s) #s
#define sbld_stringify(s) sbld_xstringify(s)

#endif
