*****************
Command reference
*****************

Invocation of the ``sb`` command is central to the usage of
simplebuild. Additionally two other commands, ``sbenv`` and ``sbrun``, are
provided for convenience. All of these commands have builtin documentation
accessible from the command itself (e.g. ``sb --help`` or ``sb --h``). For
completeness, the documentation is repeated in the following sections.

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

The ``sbenv`` command can be used to prefix any other command, causing both a
build and (if successful) the command to be invoked. This is convenient when
one is repeatedly running the same command while editing C or C++ code that
needs to be recompiled each time.

Thus running ``sbrun mycmd arg1 arg2`` is similar to running ``sb && sbenv mycmd
arg1 arg2``.

.. include:: ../build/autogen_sbrun_help.txt
  :literal:
