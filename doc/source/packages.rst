********
Packages
********
..
  Note do NOT change the above section title without updating the internal links
  to it as well!

.. include:: wipwarning.rst

Technically speaking, a simplebuild *package* is a directory with various code
and data files. The name of the package is defined by the actual name of the
directory, and should usually be CamelCased. At minimum a package directory
should contain a ``pkg.info`` file, with information about which (if any) other
packages and external software (e.g. Geant4, ZLib, Numpy, ...) is needed by the
package. In practice, most packages additionally contain some sort of code or
data files. The content and layout of packages is governed by some rules, which
will be discussed in the following, after briefly introducing the concept of
package *bundles*.

Package bundles
===============

All packages belong to a given *bundle*, which normally is defined by all the
files under a given directory (a *package root*) in which a *simplebuild.cfg*
file is located (more about such files `here
<./simplebuilddotcfg.html>`_). Typically, users will have their own working
directories (normally a GIT repository) which contains a *simplebuild.cfg* file,
and under which various subdirectories define the actual *packages*. Other
package bundles might be available on the system, and through settings in the
*simplebuild.cfg* file, packages in such bundles can be enabled as well. For
instance, common package bundles are:

FIXME: Table:

Bundle name notes
core        Provides a single package ``Core``. This special bundle is always enabled.
core_val    Provides packages with common unit tests.
dgcode      Provides packages for the `dgcode framework <LINK FIXME>`_.
dgcode_val  Provides packages with unit tests for the `dgcode framework <LINK FIXME>`_.

Note that the ``core`` bundle provides a single package named ``Core``. This special
bundle is always enabled, and all packages will automatically get a dependency
on the ``Core`` package. Additionally note that the ``dgcode`` bundles mentioned
above, are only available if ``simplebuild-dgcode`` has been installed on the
system (FIXME link).

Format of the pkg.info file
===========================

The name of the package is given by the name of the directory in which it is
located, and at the very least it must contain one file called ``pkg.info``, which
in the first line contains information about which optional externals (ROOT,
Geant4, Fortran, ...) the package needs and which other packages it depends on,
if any. The latter is important for proper build order and link-time
dependencies, so if for example PkgA depends on PkgB, then binaries and
libraries in PkgA will be linked against the library (if any) from PkgB, and any
public header files of PkgB will be available for inclusion in files in PkgA. In
the following lines it can (should) provide brief description of the purpose of
the package and information about who is the principal contact person for the
package.

In the simplest case where a package does not depend on other packages, the
contents of the pkg.info file will be very simple::

  package()

  Some short description of the package goes here.

  primary author: some.person@someplace.com

Everything after the package() statement is optional free-form text, which is
only used for documentation purposes. If the package depends on other packages,
the name of those must be given after the keyword ``USEPKG`` inside the
``package()`` declaration. So if for example the package for example depends on
other packages named ``SomeOtherPkg`` and ``AnotherPkg``, the first line of pkg.info
would look like::

  package(USEPKG SomeOtherPkg AnotherPkg)

Note: Even if not specified, all packages will implicitly depend on the package
named ``Core``, which is useful since most packages will need utilities found in
that package (for instance, all Python modules written in C++ via pybind11 are
assumed to include the C++ header file ``"Core/Python.hh"``).

If the package needs one of the external optional dependencies (such as
``Geant4``, ``ROOT``, ``HDF5``, ``Fortran``, etc.), those are specified after a ``USEEXT``
keyword::

  package(USEEXT ROOT Fortran)

Naturally, ``USEPKG`` and ``USEEXT`` can be combined::

  package(USEPKG CoolPackage Utils USEEXT Geant4)

In this example, the package needs ``Geant4`` and depends on two other packages,
``CoolPackage`` and ``Utils``.

To see a graphical representation of all available packages and the dependencies
between them, type ``sb --pkggraph`` (requires the *dot* command from the
*graphviz* bundle which must be installed on your system). To focus just on
enabled pkgs, instead do ``sb --activegraph``.

Note that the author(s) of the code indicated in this file is to be contacted
for proper acknowledgement in case the package is used to produce new scientific
results.

Components of a package
=======================

A package with just a pkg.info file is not in itself very interesting. Obviously
the package must provide something more, the possibilities for that are listed
here.

Note in general, simplebuild requires the following convention for file formats:

- C++ : .hh (headers) .icc (inline definitions) .cc (source)
- C : .h (headers) .c (source)
- Fortran : .f
- Python : .py

Even if you are used to using other extensions, it is important that you use the
ones mentioned above, because otherwise the configuration and build mechanics
will not work. Note that any directory is only allowed to contain files from one
language.

Note that the C++ and C code will by default be compiled with the formats C++17
and C99, respectively. Also note that in order to benefit maximally from the
capabilities of modern compilers to detect problematic code, simplebuild
enforces rather strict compilation flags, allows no warnings, etc.

Header files (C++/C)
--------------------

If your package needs to provide public header files, they must be created in a
subdirectory of your package called ``libinc/``. Any header file,
e.g. MyHeaderFile.hh, placed here can be included from your own packages or from
other packages depending on your package by:

.. code-block:: c++

  #include "PkgName/MyHeaderFile.hh"

Shared libraries (C++/C)
------------------------

If your package needs to provide a library written in either C++ or C, you must
create a subdirectory of your package called ``libsrc/`` and place any files
there. It will obviously mean at least one source file (.cc or .c), but also any
associated header files (unless users of your library need to be able to include
them, in which case they go in libinc/.

Binary applications (C++/C/Fortran)
-----------------------------------

There is no limit to the number of compiled programs which can be provided by
one package. Source and header files for each such program must be placed inside
a directory whose name begins with ``app_`` followed by a unique app name (unique
within the package). To avoid clashes between applications in different
packages, the final name of the binary will be prefixed with ``sb_<package name
in lower case>_<unique app name>``. Thus, if files for an application is placed
within a directory named ``app_dosomething`` in a package named MyPackage, then the
actual name of the final program which can be launched by typing it at the
command line will be ``sb_mypackage_dosomething``.

Hint: After simplebuild is finished, you can type ``sb_`` at the command line and
then hit the TAB key to get a list of all resulting applications you can run
(this also includes scripts, see below).

In order to have a program run as an automatic test (when ``sb -t`` is invoked),
then either the unique part of the name of the directory must start with
``test`` (i.e. the directory must be of the form app_testxxx/) or a reference
log-file named test.log must be placed inside the directory (more about tests
below).

Pure python modules
-------------------

Pure Python modules (``*.py``) must be placed inside a subdirectory of the package
named ``python``. Each file will correspond to a submodule of a module with the
same name as your package. In other words, if you in the package ``MyPackage``
place a file ``mystuff.py`` inside the ``python/`` subdirectory, then clients in the
form of python scripts or other python (sub)modules can import your code by:

.. code-block:: python

  import MyPackage.mystuff

Note that if you do not provide an ``__init__.py`` file yourself, one will be
created automatically.

Compiled python modules
-----------------------

If you wish to have python modules written in C++ (either for efficiency or
because you wish to make C++ functionality accessible to Python scripts), you
must create sub directories named ``pycpp_<modulename>`` Inside you must have at
least one C++ source file in which you ``#include "Core/Python.hh"`` and which contains
a PYTHON_MODULE section. Here is a very basic example of how to make
"somecppfunc" callable from python:

.. code-block:: C++

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
    mod.def("somecppfunc", &somecppfunc );
  }

Each ``pycpp_<modulename>`` sub directory will provide one python submodule. So
if you for instance have a ``pycpp_mymod/`` subdir in a package MyPackage, then it
will result in a python module ``MyPackage.mymod`` which can be imported in the
usual fashion:

.. code-block:: python

  import MyPackage.mymod

These C++-Python bindings are in fact implemented with `pybind
<https://pybind11.readthedocs.io/en/stable/basics.html>`_, with the
``Core/Python.hh`` header mostly just defining the ``PYTHON_MODULE`` macro and
introducing the convenience namespace alias ``py=pybind11``.


Compiled ``__init__.py``
------------------------

Python does not as such support compiled ``__init__.py`` files, but it is
possible to achieve the same effect by creating a compiled submodule named
``_init`` and in ``__init__.py`` have a line:

.. code-block:: python

  from _init import *

This is automatically done by simplebuild if it anyway has to create an
``__init__.py`` file (i.e. no such file is provided by the users) and there is a
compiled module named ``_init``, i.e. defined in a subdirectory named
``pycpp__init`` (notice the double underscore in the subdirectory name).

Scripts (Python/BASH)
---------------------

Of course, applications do not have to be compiled from C++, C or Fortran, but
can equally well just be a script written in for instance BASH or Python. Simply
place such scripts inside a subdirectory named ``scripts/``. Make sure that any
BASH script starts with the line::

  #!/usr/bin/env bash

and that any python scripts starts with (always refer to ``python3`` never just
``python`` since some systems still have ``python`` as an alias for ``python2``)::

  #!/usr/bin/env python3

As for compiled programs, any scripts will after installation be prefixed with
``sb_<package name in lowercase>``. Likewise, scripts can be marked as being a
test (to run when ``sb -t`` is invoked) by either prefixing their names with the
word ``test`` or by placing a reference log file next to them: If the script is
placed in a file ``script/myscript`` in the package MyPackage, then it will be
able to be invoked after build by typing sb_mypackage_myscript and any test
reference log file must be placed in ``script/myscript.log``.

Data files
----------

In addition to code in the form of programs, scripts, header files and python
modules, packages can make any kind of data file accessible to programs by
placing data files in the ``data/`` sub directory.

This could for example be small data files to be used for input to various
tests, but do note that Git repositories are **NOT** suitable for large files,
especially not when binary. Thus, try to keep files in the data/ directory less
than O(100 kilobytes) if you are working in a shared Git repository.

Data files will be available at a path given by:
``$SBLD_DATA_DIR/<packagename>/<datafilename>``

Utilities are also provided by the Core package for constructing such file paths
from C++, Python or BASH as the following examples of how to find the file
``somefile.mcpl`` from the package ``MyPackage`` show:

* **Locating data files from C++**:

  .. code-block:: C++

    #include "Core/FindData.hh"
    //...
    std::string datafile = Core::findData("MyPackage","somefile.mcpl");

* **Locating data files from python**:

  .. code-block:: python

    #option A (returns pathlib.Path):
    import Core.FindData3
    datafile = Core.FindData3("MyPackage","somefile.mcpl")
    #option B (returns str):
    import Core.FindData
    datafile = Core.FindData("MyPackage","somefile.mcpl")

* **Locating data files from the command line**:

  .. code-block:: bash

    #option A:
    DATAFILE="$SBLD_DATA_DIR/MyPackage/somefile.mcpl"
    #option B:
    DATAFILE=$(sb_core_finddata MyPackage somefile.mcpl)

.. _sbtests:

Tests
-----

As mentioned above, programs, either in the form of compiled C++/C/Fortran
programs or Python/BASH scripts can be marked as "tests" and optionally
reference log files can be provided. This serves the very important purpose on
being able to validate the functionality of our code. This is super useful in at
least two typical scenarios:

* After making changes to code, one can quickly validate that they did not break
  existing functionality. And if something was broken, tests are hopefully
  fine-grained enough that one immediately can figure out what went wrong.
* When installing the software on a new platform (i.e. a new flavour of Linux or
  OSX, or new versions of e.g. compilers, Geant4 or ROOT).

Of course, for the above goals to be achieved, it is important to have a high
test coverage. I.e. most packages should have one or two tests which very
quickly can test the basic functionality provided by the package. It does not
have to take a lot of time to develop a test, since most of the time you will
anyway have created small scripts and programs during development of a
package. Simply tidy them up a bit and mark them as a test.

If you do **not** provide a test, then you can't really complain if someone else
working on the same project makes some changes which negatively influences the
behaviour of your code. Their changes might after all have been done somewhere
which seems to be unrelated, and they might not even have considered to
double-check that your code still works afterwards. Heck, they might not even
know the purpose of your code well enough to test it.

In conclusion, tests ensure:

-  Code quality, efficient use of manpower.
-  Ability for many people to work together without friction
-  Ability to quickly validate installations on new platforms.

Any application or script whose invokable name (apart from the
``sb_<packagename>_`` part) starts with the word ``test`` will be marked as a
test, and so will any application or script who has a reference log-file
provided (either a ``test.log`` file in the ``app_XXX/`` directory or a
``scripts/myscript.log`` file for a script named ``scripts/myscript``). Tests
consists of two parts: First of all, it must finish with an exit code of 0, and
second of all those tests which have a reference log-file must give the same
output as that given in the log-file. Thus, do not print out pointer addresses
or absolute file-paths in a test with a reference log, since those will change
spuriously between invocations and when your package code was checked out in
different locations.

Ideally, tests should run in "a few seconds", to keep the combined running time
within a practical and comfortable range.
