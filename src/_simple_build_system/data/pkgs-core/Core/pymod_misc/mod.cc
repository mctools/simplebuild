#include "sbldpy/sbldpy.hh"

namespace {
  bool is_debug_build()
  {
#ifndef NDEBUG
    return true;
#else
    return false;
#endif
  }
}

SBLDPY_MODULE( misc )
{
  m.def( "is_debug_build", &is_debug_build,
         "Whether the code was built in debug mode (i.e. without NDEBUG)" );
}
