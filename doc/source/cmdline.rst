*****************
Command reference
*****************

Invocation of the ``sb`` command is central to the usage of
simplebuild. Additionally two other commands, ``sbenv`` and ``sbrun``, are
provided for convenience. All of these commands have builtin documentation
accessible from the command itself (e.g. ``sb --help`` or ``sb --h``). For
completeness, the documentation is repeated in the following sections.

.. _sbbuildvariants:

Build variants
==============

The build mode (release, reldbg, or debug) and any extra compilation or link
flags are normally taken from the ``[build]`` section of the :ref:`simplebuild
cfg file <sbdotcfg>`. The combination of these is referred to as the *build
variant*. All of the commands ``sb``, ``sbrun``, and ``sbenv`` support the
following flags for selecting a different build variant:

* ``-r``: Use build mode ``release``.
* ``-g``: Use build mode ``reldbg``.
* ``-d``: Use build mode ``debug``.
* ``-x``: Ignore any ``extra_cflags`` and ``extra_ldflags`` from the cfg file.
* ``-X NAME``: Use the extra flags of the flag set ``NAME`` from the
  ``flagsets`` table of the ``[build]`` section of the cfg file, instead of
  ``extra_cflags`` and ``extra_ldflags``.

At most one of ``-r``, ``-g``, and ``-d`` can be used, but they can be combined
with ``-x`` or ``-X NAME``, e.g. ``sb -dx``, ``sb -d -x``, ``sb -dX fma``, or
``sb -d -X fma``. The ``-x`` and ``-X`` flags can not be used together. For ``sbrun`` and ``sbenv``, the
flags must be placed before the command to run, since all arguments after it
are passed on to that command. For instance, in ``sbrun -d mycmd -x`` the
``-d`` selects the debug build variant, while ``-x`` is passed on to ``mycmd``.

Each build variant uses its own build and installation directories in the
cache directory, so switching between them (e.g. between ``sb`` and ``sb -d``)
does not throw away any previous build output. To limit disk usage, at most
``max_cachedirs`` (default 5) build variants are kept in the cache directory,
and the least recently used ones are automatically removed when needed. The
``sb -c`` command removes the build output of all build variants, while for
instance ``sb -c debug`` only removes that of the variants with the build mode
``debug``, and ``sb -c ubsan`` that of the variants with the extra flags of the
flag set ``ubsan``. Use ``sb -s`` to see which build variants are in the cache
directory (see :ref:`below <sbinspectcfg>`).

Note that the outcome of any of these commands only depends on the code, the
simplebuild cfg file, and the command line arguments. In particular, it never
depends on which build variant was used in a previous command. So if you for
instance build with ``sb -d``, you must also run your commands with ``sbenv -d
mycmd`` or ``sbrun -d mycmd`` to use the resulting debug build. Likewise, ``eval
"$(sb -d --env-setup)"`` sets up the environment for the debug build. If you
use the ``sb`` shell function (see :ref:`here <sbmanualenvsetup>`), it sets up
the environment after each build, for the build variant used in that build.

.. _sbinspectcfg:

Inspecting the configuration
============================

The ``sb -s`` command (or ``sb --summary``) prints a summary of the
configuration of the selected build variant: the cfg files and bundles used,
the package search path, the number of packages, the build mode and extra
flags (and where they come from), the cache directories, and the external
dependencies. Nothing is built, and the cache directories are not modified. As
for a build, the build variant flags can be used (e.g. ``sb -s -d``). The output
consists of ``KEY : VALUE`` lines, with the values of lists continuing on the
following lines:

.. code-block:: text

  main_cfg_file          : /path/to/myproject/simplebuild.cfg
  bundles                : myproject
                           dgcode
                           core
  ...
  build.mode             : debug
  build.mode_from        : -d
  build.extra_cflags     : -mfma
  ...
  extdeps.present        : Geant4 11.4.3
                           NCrystal 4.4.6
  extdeps.missing        : ROOT
  extdeps.unused         : HDF5

The text output ends with an overview of the cache directories of all build
variants currently in the cache directory, with their sizes on disk. Each
variant is shown with its build mode and extra flags, preceded by the name of
the flag set if it matches one that can be selected with ``-X NAME``.

The external dependencies are only known after the environment has been
inspected (which happens at the first build of the build variant). Use ``sb -s
-e`` to inspect it if needed, without building anything. External dependencies
which are not used by any packages are not inspected, and are listed as
``extdeps.unused``.

All the information is also available in JSON format with ``sb -s=json`` (or
``sb -s json``), and single values can be printed with ``sb --showcfg KEY``,
where ``KEY`` is one of the keys shown by ``sb -s``, or a key path in the JSON
output, for instance:

.. code-block:: sh

  sb --showcfg build.mode
  sb --showcfg -d variant.installdir
  sb --showcfg extdeps.Geant4.version

Values which are lists are printed one per line, and tables as ``KEY : VALUE``
lines.

The same information is installed by each build, and is available from Python
code in the packages via the ``simplebuild.cfg`` module, as the dictionary
``simplebuild.cfg.info`` (the same as the output of ``sb -s=json`` for the build
variant). For convenience, the module also provides some of the values directly:
``build_mode``, ``extra_cflags``, ``extra_ldflags``, ``flagset``, ``bundles``,
``main_cfg_file``, and ``extdeps``. For instance:

.. code-block:: python

  import simplebuild.cfg
  if simplebuild.cfg.build_mode == 'debug':
      print('This is a debug build')
  geant4 = simplebuild.cfg.extdeps['Geant4']
  if geant4['present']:
      print('Geant4 version:', geant4['version'])

The module also provides information about all packages in
``simplebuild.cfg.pkgs`` (including the name of the bundle providing each
package), and the installation directories in ``simplebuild.cfg.dirs``.

The ``sb`` command
==================

.. argparse::
   :module: _simple_build_system.parse_args
   :func: get_sb_argparse_obj
   :prog: sb
   :nodefaultconst:

The ``sbenv`` command
=====================

The ``sbenv`` command can be used to prefix any other command, causing that
command to run within the :ref:`simplebuild environment <sbmanualenvsetup>`
without needing that environment to be activated for the current shell
session. *This should not be needed if you have installed simplebuild via the
simple-build-system conda package as recommended.*

Thus running ``sbenv mycmd arg1 arg2`` is similar to running ``eval "$(sb
--env--setup)" && mycmd arg1 arg2`` in a sub-shell.

.. include:: ../build/autogen_sbenv_help.txt
  :literal:

The ``sbrun`` command
=====================

The ``sbrun`` command can be used to prefix any other command, causing both a
build and (if successful) the command to be invoked. This is convenient when
one is repeatedly running the same command while editing C or C++ code that
needs to be recompiled each time.

Thus running ``sbrun mycmd arg1 arg2`` is similar to running ``sb && sbenv mycmd
arg1 arg2``.

.. include:: ../build/autogen_sbrun_help.txt
  :literal:
