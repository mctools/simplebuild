#include "Core/Python.hh"

int main(int,char**) {

  //Test that python can be initialised from compiled code.

  pyextra::ensurePyInit();
  if ( py::len(pyextra::pyimport("sys").attr("argv")) != 1 )
    return 1;

  return 0;
}
