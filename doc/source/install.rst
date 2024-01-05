Installation
************

.. include:: wipwarning.rst

The simplebuild system is supported only on unix systems (macOS and Linux),
although it most likely will also work on Windows under the WSL (Windows
Subsystem for Linux) with a virtual Ubuntu installation. It is used exclusively
by entering commands in a terminal interface, so be sure you are familiar with
such command line interfaces.

.. note::
   The instructions here concern an installation of the basic simplebuild
   system. Users who will be using simplebuild with the Geant4-based framework
   in the "dgcode" set of packages, should simply skip the instructions here and
   instead follow the instructions for how to install both simplebuild and
   "dgcode" on:

   https://some/where/else/fixme/

Install via conda
=================

The recommended way to install simplebuild, is by installing the conda-forge
package "simple-build-system", using a conda environment .yml file like:

.. include:: ../../resources/conda_sbenv.yml
  :literal:

You can download the above recipe file here: :download:`conda_sbenv.yml <../../resources/conda_sbenv.yml>`.

.. note::
   The usage of `pip` in the above recipe is a temporary workaround until
   https://github.com/conda-forge/staged-recipes/pull/24408 is accepted.

To use it, you must first install conda. The recommendation is to use `Miniconda
<https://docs.conda.io/projects/miniconda/>`_, but if you already have another
not-too-ancient conda installation on your system, you could probably use that
instead. Then, download :download:`conda_sbenv.yml
<../../resources/conda_sbenv.yml>` and run the command::

  conda env create -f conda_sbenv.yml

Do not forget that you must activate your newly created environment before using
it for the first time in a given terminal session::

  conda activate sbenv

.. note::
   FIXME: Mention bashrc snippets and/or env-setup (link to specific subpage).



Alternative installation
========================

The conda recipe above is intended to give a self-contained and reproducible
environment with not only simplebuild itself, but also any required tools like a
Python interpreter and all the necessary build tools. For special use-cases,
experts might simply want to add the simplebuild code itself into an environment
where they otherwise have ensured that all of these third-party tools are
already available. In such a case, one can simply install simplebuild itself via
pip, either via a PyPI package (current version |pypistatus_simplebuildsystem|_)::

  python3 -mpip install simple-build-system

Or, directly from the latest simplebuild sources at github::

  python3 -mpip install git+https://github.com/mctools/simplebuild

With this latter approach, one can even install a specific commit id, branch, or
tag by appending ``@<gitid>`` to the URL in the last command. For instance::

  python3 -mpip install git+https://github.com/mctools/simplebuild@some_experimental_branch

.. |pypistatus_simplebuildsystem| image:: https://img.shields.io/pypi/v/simple-build-system.svg
.. _pypistatus_simplebuildsystem: https://pypi.org/project/simple-build-system

Verifying an installation
=========================

As a very basic verification of a simplebuild installation, one can create a
simple simplebuild project and launch a few basic unit tests (you can remove the
leftover ``sbverify`` directory afterwards:

.. literalinclude:: ./sbverify_sampleoutput.txt
   :emphasize-lines: 1-5

The important thing to notice here is that several unit tests were launched, and
the message ``All tests completed without failures!`` tells us that they all
completed without problems.
