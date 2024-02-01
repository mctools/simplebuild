************
Installation
************

The simplebuild system is supported only on unix systems (macOS and Linux),
although it most likely will also work on Windows under the WSL (Windows
Subsystem for Linux) with a virtual Ubuntu installation. It is used exclusively
by entering shell commands in a terminal interface, so be sure you are familiar
with such command line interfaces.

.. note::
   The instructions here concern an installation of the basic simplebuild
   system. Users who will be using simplebuild with the Geant4-based framework
   in the "dgcode" set of packages, should simply skip the instructions here and
   instead follow the instructions for how to install both simplebuild and
   "dgcode" on https://mctools.github.io/simplebuild-dgcode/install.html.

Install via conda
=================

*Current status:* |sbcondastatus|_ |sbcondaplatforms|_

.. |sbcondastatus| image:: https://img.shields.io/conda/vn/conda-forge/simple-build-system.svg
.. _sbcondastatus: https://anaconda.org/conda-forge/simple-build-system

.. |sbcondaplatforms| image:: https://img.shields.io/conda/pn/conda-forge/simple-build-system.svg
.. _sbcondaplatforms: https://anaconda.org/conda-forge/simple-build-system

The recommended and easiest way to install simplebuild, is by installing the
conda-forge package ``simple-build-system`` (plus at least ``compilers``), using
a conda environment ``.yml`` file like:

.. include:: ../../resources/conda_sbenv.yml
  :literal:

You can download the above recipe file here: :download:`conda_sbenv.yml <../../resources/conda_sbenv.yml>`.

To use it, you must first install conda. Instructions for how to do that is
beyond the scope of the present documentation, but in general this can be done
in a variety of ways (installing Miniforge, Miniconda, Anaconda, or even via
Homebrew). If you don't have conda installed already and do not have any other
reason for a preference, we would recommend to use `Miniforge
<https://github.com/conda-forge/miniforge>`__ since it is light-weight and
supposedly has the fewest legal concerns.

After you have conda installed, download :download:`conda_sbenv.yml
<../../resources/conda_sbenv.yml>` and run the command::

  conda env create -f conda_sbenv.yml

Do not forget that you must activate your newly created environment before using
it for the first time in a given terminal session::

  conda activate sbenv


Alternatives for experts
========================

The conda recipe above is intended to give a self-contained and reproducible
environment with not only simplebuild itself, but also any required tools like a
Python interpreter and all the necessary build tools. For special advanced
use-cases, experts might simply want to add the simplebuild code itself into an
environment where they otherwise have ensured that all of these third-party
tools are already available. In such a case, one can simply install simplebuild
itself via ``pip``, either via a PyPI package (current version
|pypistatus_simplebuildsystem|_)::

  python3 -mpip install simple-build-system

Or, directly from the latest simplebuild sources at GitHub::

  python3 -mpip install git+https://github.com/mctools/simplebuild

With this latter approach, one can even install a specific commit id, branch, or
tag by appending ``@<gitid>`` to the URL in the last command. For instance::

  python3 -mpip install git+https://github.com/mctools/simplebuild@some_experimental_branch

.. |pypistatus_simplebuildsystem| image:: https://img.shields.io/pypi/v/simple-build-system.svg
.. _pypistatus_simplebuildsystem: https://pypi.org/project/simple-build-system

.. _sbmanualenvsetup:

Note about the installed simplebuild environment: when installing via ``pip``,
one downside of not using the conda packages is the lack of automatic activation
of projects built with ``sb`` (i.e. commands ``sb_mypkg_mycmd`` will not be in
your ``PATH``, and so on). In conda, this is handled by automatically injecting
a sneaky shell function named ``sb`` into your shell session when you activate
the conda environment. When not using the conda ``simple-build-system`` package,
you have two options:

1. Do not get anything done automatically, and resort to either running ``eval "$(sb
   --env-setup)"`` when needed or prefixing all of your commands with ``sbenv``
   (i.e. run ``sbenv sb_mypkg_mycmd``).
2. Download :download:`this shell snippet <../../resources/shellrc_snippet.sh>`
   and either source it or copy and paste it into the end of the appropriate
   file shell initialisation file (e.g. ``~/.bashrc`` on Ubuntu or ``~/.zshrc``
   on macOS).


Verifying an installation
=========================

As a very basic verification of a simplebuild installation, one can create a
simple simplebuild project and launch a few basic unit tests from the
:sbpkg:`bundleroot::core_val` bundle (you can remove the leftover ``sbverify``
directory afterwards):

.. literalinclude:: ../build/autogen_sbverify_cmdout.txt

The important thing to notice here is that several unit tests were launched, and
the message ``All tests completed without failures!`` tells us that they all
completed without problems.
