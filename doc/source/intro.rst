****************************
Introduction and terminology
****************************

The simplebuild system is intended to allow individuals or groups of users to
keep track of an ever-growing collection of loosely connected files, written in
various languages such as C++, C, Python, Fortran or BASH. For reasons of
organisation, workflow and collaboration, these files are kept (usually in a Git
repo) in a directory structure used to define various units of software. The
simplebuild terminology used to refer to such a unit of code is a
*package*. Each package will contain the various bits of code, scripts, data
files, etc. which concerns one aspect of a given task or software
domain. Packages are allowed to depend on and use software from other packages,
which gives a natural way for multiple developers to collaborate on software
together while avoiding duplication of work and (hopefully) ensuring more tested
and bug-free code overall. For instance, if files in PkgB needs something (like
a header file, a library, or a Python module) from PkgA, PkgB is said to
*depend* on PkgA. Such concept of interdependent packages are of course common
in software development, but packages in simplebuild are meant to be easy to
create even for scientific users with little SW-engineering experience.

At a technical level, the simplebuild system provides the user with a single
command, ``sb`` which can be invoked in order to assemble a user's code files into
final products: commands that the user can then invoke, Python modules, data
files, etc. A *package* is simply a directory in which code source and data
files are placed in various subdirectories, depending on their type and intended
usage. The details of how files are organised in packages are provided in the
:ref:`Packages <sbpackages>` section.

A collection of related packages is referred to as a package
*bundle*. Additionally, we will occasionally also use the looser term "project"
to refer to all the code developed and used in the context of a particular
task. In this sense, code associated with a particular project will typically be
contained in one or more packages, and these packages will mostly reside inside
a particular bundle. Depending on the choice, a given simplebuild bundle might
contain only the packages of a single project, or it might contain packages
associated with multiple projects. The latter scenario might for instance be the
case when a particular group of people working on multiple loosely-connected
projects want to keep all their code in a single repository, and make it easy to
access code from multiple projects simultaneously.

Technically, the directories of all packages in a given package bundle will be
organised under a single top-level directory which is called the *package root*
of the bundle. This top-level directory of a bundle will contain a single
configuration file named ``simplebuild.cfg``. In the simplest case, the
``simplebuild.cfg`` file can be kept empty, but if desired, users can modify it
in order to customise aspects of their build, to name their bundle, or to add in
dependencies on other bundles of packages (the original bundle will then be
referred to as the *main bundle* and the associated ``simplebuild.cfg`` file is
the ``main cfg file``). Many users will not need to create such files
themselves, but will simply be told to check out a given Git repository, which
already contain a package bundle and an associated ``simplebuild.cfg``
file. Otherwise, if the intention is to start an entirely new bundle, one can
simply run ``sb --init`` in an empty directory to create a skeleton
``simplebuild.cfg`` file which can be edited later as desired. More details are
provided in the dedicated sections on :ref:`simplebuild.cfg <sbdotcfg>` and `sb
-\-init <./cmdline.html#new-bundle-initialisation-options>`_.


Upon launching the ``sb`` command inside the package root directory, simplebuild
will then analyse the ``simplebuild.cfg`` file and the files in all the
packages, in order to determine what is needed to be built and how to do it --
and it will then immediately build it and make it available. Behind the scenes,
it will use CMake to inspect the system, and determine the appropriate flags for
compilation and linking where appropriate. One noteworthy feature is that this
also facilitates the creation of Python modules written in C++ via pybind11,
making it particularly convenient to work in a mixed-language environment.

The end result is an environment in which the user can easily run their
commands, which can be written in Python, C, C++, Fortran, or BASH. The ability
to have code in separate packages, and even under separate package roots,
additionally allow domain specific experts to provide software for easy usage by
other users. One example of such a scenario is "dgcode", a bundle of simplebuild
packages intended to simplify the Geant4-based simulation work of the ESS
Detector Group (for more details about dgcode, refer to the website
https://mctools.github.io/simplebuild-dgcode/). The dgcode bundle itself
provides utilities for configuring and using Geant4, with all the necessary
domain specific tweaks and utilities. Code relating to the simulation of
specific detector prototypes is then kept in separate bundles, some publically
available in repositories on GitHub, and some kept on private GitLab servers
(mostly for historical reasons).
