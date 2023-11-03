#include "Core/Python.hh"

namespace {
  namespace Core {
    bool is_debug_build()
    {
#ifndef NDEBUG
      return true;
#else
      return false;
#endif
    }
  }
}

PYTHON_MODULE( mod )
{
  mod.def("is_debug_build",&Core::is_debug_build);
}
