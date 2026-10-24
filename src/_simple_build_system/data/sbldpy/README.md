# sbldpy

Ultra lightweight Python bindings for C++ code, based on ctypes. This
directory is self-contained:

- `include/sbldpy/sbldpy.hh`: Header-only C++17 library, used to define
  modules (with `SBLDPY_MODULE`).
- `python/sbldpy.py`: Pure-Python runtime, which loads the module libraries
  with ctypes.

The C++ code of a module is not compiled with Python headers and not linked
with libpython. A module library only exports four plain C functions (and
exceptions never cross them):

- `int sbldpy_abi_version()`: Version of the binary interface (must match
  `sbldpy.abi_version` in the runtime).
- `const char * sbldpy_module_info()`: JSON description of the module
  (versions, functions, classes, type descriptors, argument names,
  documentation, and IDs of hidden entries), or NULL on errors.
- `int sbldpy_call( int id, void ** args, void * result )`: Calls entry `id`
  of the module, returning an error code (0 on success).
- `const char * sbldpy_last_error()`: Error message of the last failed call on
  the current thread.

Strings and arrays returned from C++ are kept alive in a per-thread slot until
the next call returning such data on the same thread, and are copied
immediately by the runtime. Python callables are passed as tokens, with calls
and releases going through two C function pointers given to each module by
the runtime when it is loaded.

In simplebuild, modules are defined in `pymod_<modulename>` subdirectories of
packages. The library of a module is installed as `_sbldpy_<modulename>.so`,
next to a generated `<modulename>.py` file.
See the simplebuild documentation for how to use sbldpy.
