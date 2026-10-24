#include "sbldpy/sbldpy.hh"
#include "Core/FPE.hh"

//Compiled part of the Core.FPE module (see python/FPE.py).

SBLDPY_MODULE( _fpe )
{
  m.def( "catch_fpe", &Core::catch_fpe );
  m.def( "disable_catch_fpe", &Core::disable_catch_fpe );
  m.def( "reenable_catch_fpe", &Core::reenable_catch_fpe );
}
