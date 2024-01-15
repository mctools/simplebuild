*************
Usage example
*************

Before diving into all the details in later sections, we will in the following
go through a small usage example. The code in this example will not do anything
useful in itself, and is merely meant to illustrate how one might lay out files
for a given project, use the main simplebuild command `sb` to configure and
build everything, and finally invoke a few of the resulting commands.

Example project files
=====================

The following lists all the files in our little (silly) user project. Our
example directory contains a ``simplebuild.cfg`` file, as well as three
"packages", named ``SomePkgA``, ``SomePkgB``, and ``SomePkgC`` - each kept in
their separate subdirectory of the same name as the package (the subdirectory
name actually *defines* the name of the package). In addition to code files,
each package subdirectory contains a ``pkg.info`` file, with information about
the dependencies of the given package.

.. include:: ../build/autogen_projectexample_files.rst

Building the project
====================

To build our example project, we simply step into the project directory where we
have the ``simplebuild.cfg`` file by issuing a command like ``cd
/some/where/example_project`` (it is also OK to step into any sub-directory
under that directory). Then we simply invoke ``sb`` with no arguments to perform
the build (this includes both configuration, build, and installation steps of
more traditional setups):

.. include:: ../build/autogen_projectexample_cmdout_sb.txt
  :literal:

Several things happened above:

1. simplebuild searched the directory tree under ``/some/where/example_project``
   for ``pkg.info`` files to determine which simplebuild packages to
   consider. It also added the ``Core`` package (defined elsewhere in the
   ``core`` bundle), since that particular package is always required (for
   instance because it provides the ``"Core/Python.hh"`` header file).
2. It investigated each package to determine what kind of code and data files it
   provided, and established dependency relationships and other configuration
   details concerning the various pieces.
3. Behind the scenes it created a cache directory in
   ``/some/where/example_project/simplebuild_cache``, to use for any sort of temporary files
   needed for the following steps. Note that if you ever wish to clean up the
   cache files, you can simply invoke ``sb -c``.
4. It launched CMake to inspect the environment, to learn about compilers,
   configuration flags, etc. It also specifically looked in the environment for
   ``ZLib`` since one of our packages (``SomePkgC``) had listed that as an
   external dependency. It took several seconds, but the result are cached for
   future reusage.
5. It went ahead and actually *built* our various code files into their final
   product. For C++ code that means actual compilation into binary code, copied
   into appropriate "installation folders" in the cache directory. On the other
   hand, pure data files and scripts (like our pure Python files) are merely
   symlinked into their installation folders. The advantage of symlinking
   scripts and data files, is that any future editing will be instantly applied
   without any need for another ``sb`` invocation.  The build step was actually
   a bit slow, taking many seconds. This is mostly due to compilation of the
   (pybind11-based) C++-Python bindings. One side-effect of symlinking, is that
   all script files must be executable (e.g. ``chmod +x <pathtofile>``).
6. It produced a little summary of all the operations.

.. admonition:: Environment setup for non-conda installations.
  :class: tip

   If you did not install simplebuild via the conda package, the output above
   might have included a warning about needing to invoke ``eval "$(sb
   --env-setup)"`` to setup your environment. One solution is then to simply run
   that command, or you can refer to :ref:`the relevant documentation
   <sbmanualenvsetup>` for how to address this in general.

Although the entire build process took a bit of time, the cache usage means that
if we go ahead and invoke ``sb`` once again, it will this time more or less skip
the expensive steps 4 and 5 above, and finish almost instantaneously:

.. include:: ../build/autogen_projectexample_cmdout_sb2.txt
  :literal:

If we go ahead and edit a C++ file, we must then invoke ``sb`` again, in order
to get the corresponding binary output files rebuilt. Likewise, if we are adding
or removing files to a package (or adding/removing packages), we should also
invoke ``sb`` again, to make sure the content of the installation folders are
once again up to date and consistent with the source code files. However, if we
are merely editing existing scripts or data files, this is not needed due to the
symlinking mentioned above. Now, let us see this in practice. So let us pretend
we have edited the file ``example_project/SomePkgC/app_foobar/main.cc``
(e.g. open it, add a blank line, close it - or merely use the unix ``touch``
command). We have also added a new file,
``example_project/SomePkgB/scripts/newcmd`` with the content:

.. literalinclude:: ../example_project_newcmd_content
  :language: python

Since it is a script, we have made the new file executable (``chmod +x
SomePkgB/scripts/newcmd``). If we had forgotten, ``sb`` would tell us later.

With these changes, we now invoke ``sb`` once again:

.. include:: ../build/autogen_projectexample_cmdout_sb3.txt
  :literal:

As we can see, only parts of the build related to our changes actually had to be
redone, and accordingly it was blazingly fast.

Using the project
=================

Having build our example project, let us now try to actually *use* it! As a
first example, let us try to invoke the commandline application defined in our
file ``SomePkgC/app_foobar/main.cc``. If we look carefully in the output above,
we would have noticed a line saying ``Creating application
sb_somepkgc_foobar``. In general this is how it works, all commandline
applications will end up with a name ``sb_<pkgname>_<appname>`` (lowercased)
where in this case ``<appname>`` is ``foobar`` and ``<pgname>`` lowercased is
``somepkgc``. For scripts, ``<appname>`` instead becomes the actual
filename. The reason for this naming policy is one of name-spacing: by prefixing
all commands are with ``sb_<pkgname>_``, there should be almost no chance of any
name-clashes between applications in different packages, or even with other
commands on your unix system. We can try to run it:

..
   However, if we try to simply invoke
   ``sb_somepkgc_foobar`` we get an error::

     $> sb_somepkgc_foobar
     sb_somepkgc_foobar: command not found

   In this case, the reason for the error is that the installation folder in which the
   ``sb_somepkgc_foobar`` file was placed has not added to the ``PATH`` variable of
   the unix shell. To fix this, we should do as instructed and invoke ``eval "$(sb
   --env-setup)"`` first:

.. include:: ../build/autogen_projectexample_cmdout_foobar.txt
  :literal:

.. admonition:: Environment setup for non-conda installations.
  :class: tip

   if you got a ``sb_somepkgc_foobar: command not found`` you most likely did
   not install simplebuild via conda. Refer to :ref:`the relevant documentation
   <sbmanualenvsetup>` for how to deal with this.

For completeness, here are some more examples of us using our project:

.. include:: ../build/autogen_projectexample_cmdout_other0.txt
  :literal:

.. include:: ../build/autogen_projectexample_cmdout_other1.txt
  :literal:

.. include:: ../build/autogen_projectexample_cmdout_other2.txt
  :literal:

.. include:: ../build/autogen_projectexample_cmdout_other3.txt
  :literal:

.. include:: ../build/autogen_projectexample_cmdout_other4.txt
  :literal:

Adding tests
============

As is discussed in more details :ref:`in a dedicated section <sbtests>`, it is
possible to mark certain applications or scripts as being a *test*. Launching
``sb --tests`` (or ``sb -t`` for short) will then not only build the project,
but will also launch all the tests. Any command that fails (i.e. exits with
non-zero exit code) will be marked as a test failure. Additionally, it is
possible to add text files containing the expected output of a given command. If
the actual output fails to match such a *reference log file*, it will also
result in a test failure.

Having such tests to perform a quick validation that everything still works is
tremendously useful, and here we will simply show a quick example of this in
practice. Specifically, we would like a unit test that verifies the output of
the ``mysquarefunc`` that is already a part of the ``SomePkgA.foo`` module of our
example project. Thus, we add a new file
``example_project/SomePkgA/scripts/testfoo`` with the content:

.. literalinclude:: ../example_project_newtestcmd_content
  :language: python

Again, since it is a script, we have made the new file executable (``chmod +x
SomePkgA/scripts/testfoo``). If we had forgotten, ``sb`` would tell us later.
Having added this new script, we now launch ``sb --tests``:

.. include:: ../build/autogen_projectexample_cmdout_sbtests.txt
  :literal:

All went well in this case! If you had issues, you could go and look in the
directory listed in the output (the ``Trouble info`` column) for clues as to
what went wrong. If there was a problem with a reference log (the ``Log-diff``
column), you could also use the ``sb_core_reflogupdate`` command to check what
was wrong (just don't actually update the log files unless you are the developer
maintaining them).
