#include "Core/Python.hh"
#include <stdexcept>

namespace {
  void raw_simplebuild_pyInit()
  {
    if (Py_IsInitialized())
      throw std::runtime_error("Attempt at initialising Python interpreter twice detected");
    Py_Initialize();
  }
}

void pyextra::pyInit(const char * argv0)
{
  raw_simplebuild_pyInit();
  //Always put at least a dummy entry for sys.argv[0], since some python modules
  //will assume this is always present (for instance the matplotlib tkinter
  //backend with python 3.7):
  py::list pysysargv;
  pysysargv.append(std::string(argv0?argv0:"dummyargv0"));
  pyextra::pyimport("sys").attr("argv")=pysysargv;
}

void pyextra::pyInit(int argc, char** argv)
{
  if (argc==0) {
    pyInit();
    return;
  }
  raw_simplebuild_pyInit();
  py::list pysysargv;
  for (int i = 0; i < argc; ++i)
    pysysargv.append(std::string(argv[i]));
  pyextra::pyimport("sys").attr("argv")=pysysargv;
}
