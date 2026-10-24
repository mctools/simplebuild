*************
Usage example
*************

Before diving into all the details in later sections, we will in the following
go through a small usage example. The code in this example will not do anything
useful in itself, and is merely meant to illustrate how one might lay out files
for a given project or task, use the main simplebuild command ``sb`` to
configure and build everything, and finally invoke a few of the resulting
commands.

Example project files
=====================

The following lists all the files in our little (silly) user
project. Technically, these files are spread over three simplebuild *packages*
and these packages are collected in a single simplebuild *bundle*. Our example
directory thus contains a :ref:`simplebuild.cfg <sbdotcfg>` file (exactly one
such is always associated with a *bundle*), as well as three *packages*, named
``SomePkgA``, ``SomePkgB``, and ``SomePkgC`` -- each kept in their separate
subdirectory of the same name as the package (the subdirectory name actually
*defines* the name of the package). In addition to code files, each package
subdirectory contains a ``pkg.info`` file, with information about the
dependencies of the given package.

.. include:: ../build/autogen_projectexample_files.rst

Building the project
====================

To build our example project, we simply step into the directory where we have
the :ref:`simplebuild.cfg <sbdotcfg>` file by issuing a command like ``cd
/some/where/example_project`` (it is also OK to step into any sub-directory
under that directory). Technically this directory is the *package root* of our
package *bundle*. Then we simply invoke ``sb`` with no arguments to perform the
build (this includes both configuration, build, and installation steps of more
traditional setups):

.. include:: ../build/autogen_projectexample_cmdout_sb.txt
  :literal:

Several things happened above:

1. simplebuild searched the directory tree under ``/some/where/example_project``
   for ``pkg.info`` files to determine which simplebuild packages to
   consider. It also added the :sbpkg:`Core` package (defined elsewhere in the
   :sbpkg:`bundleroot::core` bundle), since that particular package is always
   required (for instance because it provides the ``"Core/Python.hh"`` header
   file).
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

To find out where the time goes when building, ``sb --buildtimes`` shows the
slowest compilation and linking steps (and ``sb --buildtimes=N`` the N slowest),
along with the slowest packages. The timings are recorded whenever files are
built, so they reflect the most recent build of each file, and no special build
is needed. Note that the timings come from builds with several steps running in
parallel, which might inflate them a bit. Additionally, ``sb --includecosts``
(which requires the Python module numpy) estimates which files are the most
costly to compile, including header files. This is based on the build timings
and the include statements in the code: the compilation time of each file is
modelled as the sum of the costs of the files it needs (its source file, the
header files of the project it includes directly or indirectly, and the system
headers included by those), and the costs of the files are estimated from all
the timings. This can of course only give rough estimates, but is useful for
finding the worst offenders.

Using the project
=================

Having built our example project, let us now try to actually *use* it! As a
first example, let us try to invoke the commandline application defined in our
file ``SomePkgC/app_foobar/main.cc``. If we look carefully in the output above,
we can notice a line saying ``Creating application
sb_somepkgc_foobar``. In general this is how it works, all commandline
applications will end up with a name ``sb_<pkgname>_<appname>`` (lowercased)
where in this case ``<pkgname>`` lowercased is ``somepkgc`` and ``<appname>``
is ``foobar``. For scripts, ``<appname>`` instead becomes the actual
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
the ``mysquarefunc`` that is already a part of the ``SomePkgA.foo`` module of
our example's bundle. Thus, we add a new file
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
what went wrong. Adding for instance ``--testexcerpts=20`` will additionally
print the first and last 20 lines of the output of failed tests, or of the
differences between the output and the reference log.

The report of the test results can also be printed again later with ``sb
--testreport``, without building anything or running any tests (as usual, the
build variant can be selected with e.g. ``-d``, and the results of each build
variant are kept separately). The report can be customised, e.g. ``sb
--testreport=failed,time`` shows only the failed tests, with the slowest first
(other sort orders are ``name``, and ``relevance``, the default, which in
printed reports puts failed tests at the bottom, where they remain visible in
the terminal, with slower tests towards the bottom within each group),
and ``--testfilter`` and ``--testexcerpts`` can be used to select tests and show
excerpts (if ``--testfilter`` does not select any tests when running tests,
``sb`` stops with an error already before building anything). With ``sb --testreport=interactive`` (which can also be combined with
``-t``), the results can instead be browsed interactively: the output of tests,
or the differences between their output and their reference logs, can be
inspected, and tests can be run again, optionally after rebuilding (press ``?``
for a list of keys). By default, the interactive view shows running tests
first, then failed tests, tests waiting to run, and finally successful tests. When running tests, the slowest tests (as measured in
previous runs) are started first, to avoid ending up waiting for a single slow
test at the end (with ``--testorder=fastest``, the fastest tests are instead
started first, to get results as quickly as possible). To only run the tests
which can complete within a given time, use e.g. ``sb -t --testtime=10``, which
skips the slowest tests (based on previous runs) as needed to finish within
approximately 10 seconds (tests without timings from previous runs are always
run). When running tests in a
terminal, the progress is shown while they run, including an estimate of the
remaining time (based on previous runs), and pressing ``i`` opens the
interactive view, in which results appear as tests finish (finished tests can
be inspected while other tests are still running). The interactive view can
also run the shown tests again in the background (``t``).

Reference logs must match the output exactly, including whitespace. If the
output differs from a reference log only in whitespace (e.g. due to an editor
removing trailing spaces from the reference log), this is pointed out
explicitly. If there was a problem with a reference log (the ``Log-diff``
column), you can use ``sb --reflogupdate`` to review the differences in an
interactive viewer, which highlights changed words and whitespace (press ``?``
in the viewer for a list of keys). From the viewer, you can also run the test
again (``r``), or rebuild and then run the test again (``b``), for instance
after editing the code producing the output (if the build fails, its output is
shown, and it can be shown again later with ``e``). Finally, the viewer can update
the reference log in the package with the new output, but you should not
actually do so unless you are the developer maintaining it. To make you think
before updating, a randomly generated code must be typed in reverse order for
each update (for large scale maintenance, this requirement can be disabled for
the rest of the session).
