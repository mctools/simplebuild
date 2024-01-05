#include "Core/Python.hh"
#include <iostream>

namespace {
  void somecppfunc()
  {
    std::cout<<"in somecppfunc in a python module"<<std::endl;
  }
}

PYTHON_MODULE( mod )
{
  //The following binding is essentially pybind11 code:
  mod.def("somecppfunc", &somecppfunc );
}
