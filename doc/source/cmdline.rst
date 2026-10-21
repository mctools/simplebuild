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

At most one of ``-r``, ``-g``, and ``-d`` can be used, but they can be combined
with ``-x``, e.g. ``sb -dx`` or ``sb -d -x``. For ``sbrun`` and ``sbenv``, the
flags must be placed before the command to run, since all arguments after it
are passed on to that command. For instance, in ``sbrun -d mycmd -x`` the
``-d`` selects the debug build variant, while ``-x`` is passed on to ``mycmd``.

Each build variant uses its own build and installation directories in the
cache directory, so switching between them (e.g. between ``sb`` and ``sb -d``)
does not throw away any previous build output. To limit disk usage, at most
``max_cachedirs`` (default 5) build variants are kept in the cache directory,
and the least recently used ones are automatically removed when needed. The
``sb -c`` command removes the build output of all build variants.

Note that the outcome of any of these commands only depends on the code, the
simplebuild cfg file, and the command line arguments. In particular, it never
depends on which build variant was used in a previous command. So if you for
instance build with ``sb -d``, you must also run your commands with ``sbenv -d
mycmd`` or ``sbrun -d mycmd`` to use the resulting debug build. Likewise, ``eval
"$(sb -d --env-setup)"`` sets up the environment for the debug build. If you
use the ``sb`` shell function (see :ref:`here <sbmanualenvsetup>`), it sets up
the environment after each build, for the build variant used in that build.

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
