# sbldpy

Ultra lightweight Python bindings for C++ code, based on ctypes. This
directory is self-contained:

- `include/sbldpy/sbldpy.hh`: Header-only C++17 library, used to define
  modules (with `SBLDPY_MODULE`).
- `python/sbldpy.py`: Pure-Python runtime, which loads the module libraries
  with ctypes.

The C++ code of a module is not compiled with Python headers and not linked
with libpython. The runtime only uses four plain C functions of a module
library (and exceptions never cross them; see sbldpy.hh for advice about
compiling with hidden symbol visibility):

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

A module is compiled (as C++17, with `include/` in the include path) into a
shared library, and `SBLDPY_MODULE` must be used exactly once in its code. If
`SBLDPY_MODNAME` is defined (e.g. `-DSBLDPY_MODNAME=mymod`), the name given to
`SBLDPY_MODULE` must match it. The library is loaded by a small Python module
next to it, using the runtime. For instance, for a library `_sbldpy_mymod.so`
of a module `SBLDPY_MODULE( mymod )`, a file `mymod.py` next to it contains:

```python
import sbldpy as _sbldpy
_sbldpy.load_module( globals(), '_sbldpy_mymod', 'mymod' )
```
