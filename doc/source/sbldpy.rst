.. _sbsbldpy:

**********************************
Python modules with sbldpy
**********************************

.. warning::

   sbldpy is new and should be considered experimental. Details might still
   change in future releases.

sbldpy provides a simple way to make C++ functions and classes available as
Python modules. Unlike the ``pycpp_<modulename>`` subdirectories (which use
`pybind11 <https://pybind11.readthedocs.io/en/stable/basics.html>`_), the C++
code is **not** compiled with Python headers or linked with the Python library.
Instead, a small and fixed set of plain C functions is exported from a shared
library, which is loaded with the `ctypes
<https://docs.python.org/3/library/ctypes.html>`_ module of the Python standard
library. This means that the compiled code does not depend on the version of
Python, and it is in general much faster to compile.

sbldpy is deliberately ultra lightweight, so modules compile quickly. It
supports only a small set of features and types, which are always handled in
the same simple manner. In particular, data is always copied (with the
exception of arrays, which can be passed as views), and C++ functions can not
return references or pointers. More advanced functionality (e.g. default
values of arguments, properties, or alternative ways to create objects) can be
implemented in Python code wrapping the module.

Modules are defined in subdirectories named ``pymod_<modulename>`` of a
package. The ``pymod_<modulename>`` and ``pycpp_<modulename>`` subdirectories
can be used in the same package, but a module can not be provided by more
than one of ``pymod_<modulename>/``, ``pycpp_<modulename>/`` and
``python/<modulename>.py``.

Module names can start with a single underscore, which is useful for compiled
modules which are only used by Python modules wrapping them (for instance
``pymod__impl/`` provides the module ``_impl``, which a file
``python/mymod.py`` could import with ``from ._impl import somefunction``).
Two names are special: ``pymod__init/`` provides the ``__init__.py`` file of
the package, and ``pymod__main/`` provides its ``__main__.py`` file (these
files can then not be provided in other ways). The module in ``pymod__main/``
must define a function named ``main`` without parameters, which is called
when the package is run with ``python3 -m <packagename>`` (its return value,
if any, is used as exit code). Names starting with ``_sbld``
or with more than one underscore are not allowed.

Example
=======

Placing the following in the file ``pymod_mymod/mod.cc`` of a package
``MyPkg``:

.. code-block:: C++

  #include "sbldpy/sbldpy.hh"
  #include "MyPkg/Stuff.hh" // Code in the package library (optional)

  namespace {
    double add( double a, double b ) { return a + b; }
    std::string greet( const std::string& name ) { return "Hello " + name; }
    class Counter {
    public:
      Counter( std::int64_t start ) : m_value(start) {}
      std::int64_t increment( std::int64_t n ) { return m_value += n; }
      std::int64_t value() const { return m_value; }
    private:
      std::int64_t m_value;
    };
  }

  SBLDPY_MODULE( mymod )
  {
    m.doc( "My module" );
    m.def( "add", &add, "Add two numbers", { "a", "b" } );
    m.def( "greet", &greet, { "name" } );
    m.add_class<Counter>( "Counter", "A counter" )
      .def_init<std::int64_t>( { "start" } )
      .def( "increment", &Counter::increment, { "n" } )
      .def( "value", &Counter::value );
  }

results in a Python module which can be used as:

.. code-block:: python

  import MyPkg.mymod
  print( MyPkg.mymod.add( 1, 2 ) )          # 3.0
  print( MyPkg.mymod.greet( name = 'you' ) ) # Hello you
  c = MyPkg.mymod.Counter( 10 )
  c.increment( n = 1 )
  print( c.value() )                        # 11

The name given to ``SBLDPY_MODULE`` must match the name of the subdirectory,
and ``SBLDPY_MODULE`` must be used exactly once per module (the code of a
module can be spread over several files in the ``pymod_<modulename>``
directory). The functions, classes, etc. get proper signatures and
documentation in Python (try for instance ``help(MyPkg.mymod)``). Argument
names are optional, but recommended: they make it possible to pass arguments by
name in Python, which helps avoiding mistakes. Without them, arguments can only
be given positionally.

Supported types
===============

Since Python integers have no width, and to avoid issues with integer widths
on different platforms, values passed from Python to C++ must use specific
types:

.. list-table::
   :header-rows: 1

   * - Python
     - C++ parameter type
   * - ``int``
     - ``std::int64_t`` only (a value outside its range gives an
       ``OverflowError``)
   * - ``float`` (and ``int``)
     - ``double`` only
   * - ``bool`` (only ``True`` or ``False``)
     - ``bool``
   * - ``str``
     - ``std::string`` or ``const char*`` (the latter can not contain null
       characters)
   * - ``tuple`` (or list) of the above
     - ``std::tuple``, ``std::pair`` or ``std::array``
   * - Array: numpy array, other objects with the buffer protocol, or a list
     - ``sbldpy::NumpyView<const double>``, ``sbldpy::NumpyView<const
       std::int64_t>`` or ``sbldpy::NumpyView<const std::uint8_t>`` (raw
       bytes, also accepting ``bytes``, ``bytearray`` and ``memoryview``). The
       data is only valid during the call, and is not copied unless needed.
   * - Callable
     - ``sbldpy::Callback<R(Args...)>`` (see below)
   * - Object of class defined in the module
     - ``T&`` or ``const T&``

A ``TypeError`` is raised for values of the wrong type (for instance, a
``float`` is not accepted for an integer, and a ``bool`` is not accepted for
an integer or a ``float``).

Return values (C++ to Python) can be:

.. list-table::
   :header-rows: 1

   * - C++ return type
     - Python
   * - Any integer type up to 64 bits (except ``char``)
     - ``int``
   * - ``double`` or ``float``
     - ``float``
   * - ``bool``
     - ``bool``
   * - ``std::string`` (valid UTF-8)
     - ``str``
   * - ``std::tuple``, ``std::pair`` or ``std::array`` of the above, or of
       ``sbldpy::NumpyCopy``
     - ``tuple``
   * - ``sbldpy::NumpyCopy<T>``
     - New one-dimensional numpy array (copy of the data)
   * - ``sbldpy::NumpyView<T>`` or ``sbldpy::NumpyView<const T>`` (only
       from methods)
     - One-dimensional numpy array referring to the data (read-only for
       ``const T``)
   * - Object of class defined in the module (by value)
     - New object owned by Python
   * - ``void``
     - ``None``

References and pointers can not be returned, and a ``std::vector`` must be
returned as a ``sbldpy::NumpyCopy`` or ``sbldpy::NumpyView``. The element type
of numpy arrays can be any fixed width integer type, ``float`` or ``double``
(multi-dimensional arrays can be reshaped in Python). Returning
numpy arrays requires numpy, while numpy is not needed for passing arrays to
C++ functions.

A numpy array returned as a ``sbldpy::NumpyView`` from a method keeps the
Python object alive. The data must be owned by the C++ object, and the array
becomes invalid if the C++ object reallocates or destroys the data (e.g. if a
``std::vector`` is resized). Call ``.copy()`` on the array to be safe. Using
unsupported types results in a compilation error with a descriptive message.

Classes
=======

Classes are added with ``m.add_class<T>( name, doc )``, and support:

* ``.def_init<Args...>( ... )``: constructor calling ``T(Args...)``. At most
  one constructor can be defined. Without a constructor, objects can only be
  created by functions returning them.
* ``.def( name, method, ... )``: method, given as a member function pointer of
  ``T`` itself (not of a base class), or as a function or lambda taking ``T&``
  or ``const T&`` as first parameter. Methods can also have special names like
  ``__repr__``.
* ``.def_static( name, function, ... )``: static method.

Objects are owned by Python, and deleted when the Python object is deleted.
Objects can only be passed to functions of the same module, and the classes
can not be subclassed in Python. Objects can not be copied or pickled in
Python.

Callbacks
=========

Python callables can be passed to C++ functions taking a
``sbldpy::Callback<R(Args...)>`` parameter. The callback object can be copied
and stored, and the Python callable is kept alive until the last copy is
destroyed. Only plain data is passed (and copied): The parameters can be
integers (of any type up to 64 bits), ``float``, ``double``, ``bool``,
``std::string``, ``const char*``, tuples of those, and ``sbldpy::NumpyCopy`` objects. The return type
can be ``void``, ``std::int64_t``, ``double``, ``bool``, ``std::string``,
tuples of those, or ``std::vector`` of ``double``, ``std::int64_t`` or
``std::uint8_t``.

.. code-block:: C++

  double integrate( sbldpy::Callback<double(double)> f, std::int64_t n )
  {
    double s = 0.0;
    for ( std::int64_t i = 0; i < n; ++i )
      s += f( ( i + 0.5 ) / n );
    return s / n;
  }

If the Python callable raises an exception, a ``sbldpy::CallbackError`` is
thrown in C++. Unless it is caught by the C++ code, the original Python
exception is then raised again (with its traceback) when the C++ function
returns. Callbacks can call functions of the module again.

Exceptions
==========

Exceptions thrown in C++ code are converted to Python exceptions:
``std::invalid_argument``, ``std::domain_error`` and ``std::length_error``
become ``ValueError``, ``std::out_of_range`` becomes ``IndexError``,
``std::overflow_error`` becomes ``OverflowError``, ``sbldpy::TypeError``
becomes ``TypeError``, ``std::bad_alloc`` becomes ``MemoryError``, and all
other exceptions become ``RuntimeError``.

Threads
=======

Python's global interpreter lock is released during calls to C++ functions,
so C++ functions can run in parallel when called from several Python threads.
Callbacks can be invoked from any thread.

Implementation and versions
===========================

sbldpy consists of the header-only C++17 library ``sbldpy/sbldpy.hh`` and the
pure-Python runtime module ``sbldpy``. Each module library (named
``_sbldpy_<modulename>.so`` and installed next to a small generated
``<modulename>.py`` file) exports only the four plain C functions
``sbldpy_abi_version``, ``sbldpy_module_info``, ``sbldpy_call`` and
``sbldpy_last_error``. C++ exceptions never cross these functions, and Python
exceptions never cross the callbacks. The binary interface between the
modules and the runtime has a version, which is checked when modules are
loaded.

The version of sbldpy is available in C++ as ``SBLDPY_VERSION`` (an integer
which is ``major*1000000+minor*1000+patch``, e.g. ``1002003`` for version
1.2.3) and ``SBLDPY_VERSION_STR``, and in Python as ``sbldpy.version_int`` and
``sbldpy.__version__``. Information about a loaded module (including the
version of sbldpy it was built with) is available with
``sbldpy.module_info(module)``.

Python module names starting with ``_sbld`` are reserved, and can not be used for
any Python modules in packages (and a package can not be named ``sbldpy``).
