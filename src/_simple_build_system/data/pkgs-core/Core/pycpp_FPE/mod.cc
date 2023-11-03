#include "Core/FPE.hh"
#include "Core/Python.hh"

namespace Core {
  class pyDisableFPEContextManager {
  public:
    void on_enter() { Core::disable_catch_fpe(); }
    void on_exit(py::object,py::object,py::object) { Core::reenable_catch_fpe(); }
  };
}


PYTHON_MODULE( mod )
{
  mod.def("catch_fpe",&Core::catch_fpe);

  py::class_<Core::pyDisableFPEContextManager>(mod,"DisableFPEContextManager")
    .def(py::init<>())
    .def("__enter__",&Core::pyDisableFPEContextManager::on_enter)
    .def("__exit__",&Core::pyDisableFPEContextManager::on_exit)
    ;

  mod.def("disable_catch_fpe",&Core::disable_catch_fpe);
  mod.def("reenable_catch_fpe",&Core::reenable_catch_fpe);
}
