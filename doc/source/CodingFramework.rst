CodingFramework
****************

.. container::
   :name: page

   .. container:: aui-page-panel
      :name: main

      .. container::
         :name: main-header

         .. container::
            :name: breadcrumb-section

            #. `DGCode <index.html>`__

         .. rubric::  DGCode : CodingFramework
            :name: title-heading
            :class: pagetitle

      .. container:: view
         :name: content

         .. container:: page-metadata

            Created by Thomas Kittelmann, last modified on Oct 31, 2022

         .. container:: wiki-content group
            :name: main-content

            The ESS detector group needs to develop software which will have to be used in a variety of places, including Linux servers and either Linux or OSX laptops. The coding framework "dgcode" is on one hand meant to facilitate this cross-platform deployment, while at the same time simplifying the collaboration between multiple developers working on one or more tasks.

            More specifically, our coding framework is intended to be an ever-growing collection of loosely connected files, most written in various language such as C++, C, Python3, Fortran or BASH, which for reasons of organisation, workflow and collaboration are distributed in a directory structure used to define various units of software. The terminology which we use to refer to such a unit of code is a "package". Each package will contain the various bits of code (for compiled libraries and applications), scripts, reference files, etc. which concerns one aspect of a given task or software domain. Packages are allowed to depend on and use software from other packages, which gives a natural way for multiple developers to collaborate on software together while avoiding duplication of work and (hopefully) ensuring more tested and bug-free code overall.

            In addition to all the actual code in the packages, the *dgcode* framework also contains the functionality for seamlessly building and testing all the packages on both Linux and OSX.

            The separation of the core framework code (framework packages and the aforementioned building and testing functionalities) and the user-made packages is reflected in the repository layout. The code of the framework is hosted inside a `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__ repository on github.org (`overview <https://github.com/mctools/dgcode>`__, `changelog/commits <https://github.com/mctools/dgcode/commits/main>`__), while the user packages may be placed in one of the collective repositories (`DGCode Projects <https://github.com/ess-dg/dgcode_projects>`__ at GitHub for public packages, or `DGCode Private Projects <https://git.esss.dk/dgcode/dgcode_private_projects>`__ at GitLab for private ESS packages) or in the users own repositories. 

            .. container:: confluence-information-macro has-no-icon confluence-information-macro-information

               .. container:: confluence-information-macro-body

                  .. container:: toc-macro rbtoc1699357616208

                     -  `Getting started <#CodingFramework-Gettingstarted>`__

                        -  `1) Before you start <#CodingFramework-1)Beforeyoustart>`__
                        -  `2) Verify Git configuration <#CodingFramework-2)VerifyGitconfiguration>`__
                        -  `3) Getting the framework <#CodingFramework-3)Gettingtheframework>`__
                        -  `4) Creating the projects directory with a bootstrap file in it <#CodingFramework-4)Creatingtheprojectsdirectorywithabootstrapfileinit>`__

                           -  `4a) Getting the DGCode Public Projects repository <#CodingFramework-4a)GettingtheDGCodePublicProjectsrepository>`__
                           -  `4b) Getting the DGCode Private Projects repository <#CodingFramework-4b)GettingtheDGCodePrivateProjectsrepository>`__

                              -  `Note for 4a and 4b <#CodingFramework-Notefor4aand4b>`__

                           -  `4c) Setting up a new projects directory <#CodingFramework-4c)Settingupanewprojectsdirectory>`__

                        -  `5) Building the code, and running the tests <#CodingFramework-5)Buildingthecode,andrunningthetests>`__

                           -  `Failure at configuration stage - getting the right software installed <#CodingFramework-Failureatconfigurationstage-gettingtherightsoftwareinstalled>`__
                           -  `Some packages disabled due to missing Geant4, ROOT, Fortran, ... <#CodingFramework-SomepackagesdisabledduetomissingGeant4,ROOT,Fortran,...>`__

                        -  `6) Run validation tests <#CodingFramework-6)Runvalidationtests>`__
                        -  `The dgbuild command <#CodingFramework-Thedgbuildcommand>`__

                           -  `Enabling packages <#CodingFramework-Enablingpackages>`__
                           -  `Enabling packages for advanced users <#CodingFramework-Enablingpackagesforadvancedusers>`__

                     -  `Packages <#CodingFramework-Packages>`__

                        -  `Format of the pkg.info file <#CodingFramework-Formatofthepkg.infofile>`__
                        -  `Optional components of a package <#CodingFramework-Optionalcomponentsofapackage>`__

                           -  `C++/C header files <#CodingFramework-C++/Cheaderfiles>`__
                           -  `C++/C libraries <#CodingFramework-C++/Clibraries>`__
                           -  `C++/C/Fortran applications <#CodingFramework-C++/C/Fortranapplications>`__
                           -  `Pure python modules <#CodingFramework-Purepythonmodules>`__
                           -  `Compiled python modules <#CodingFramework-Compiledpythonmodules>`__

                              -  `Compiled \__init\_\_.py <#CodingFramework-Compiled__init__.py>`__

                           -  `Scripts (normally Python or BASH) <#CodingFramework-Scripts(normallyPythonorBASH)>`__
                           -  `Data files <#CodingFramework-Datafiles>`__
                           -  `Tests <#CodingFramework-Tests>`__

                     -  `Sharing your changes with other developers <#CodingFramework-Sharingyourchangeswithotherdevelopers>`__

            .. container:: confluence-information-macro confluence-information-macro-tip

               .. container:: confluence-information-macro-body

                  Please report any bugs, problems or feature requests related to the coding framework in the `GitHub Issue Tracker <https://github.com/mctools/dgcode/issues>`__. Click `HERE <https://jira.esss.lu.se/secure/CreateIssue%21default.jspa?pid=12404>`__ to report a new item.

            .. rubric:: Getting started
               :name: CodingFramework-Gettingstarted

            .. rubric:: 1) Before you start
               :name: CodingFramework-1)Beforeyoustart

            First of all, make sure you have installed at least the Basic Prerequisites as instructed on `HowToInstallComputingPrereqs <https://confluence.esss.lu.se/display/DGCODE/HowToInstallComputingPrereqs>`__ and that you have setup your Git configuration as instructed on `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__.

            .. rubric:: 2) Verify Git configuration
               :name: CodingFramework-2)VerifyGitconfiguration

            Secondly, verify once again that you have Git correctly setup by running the command:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git config --get-regexp 'user\.(name|email)'

            Check that you get a result with similar to this (but with your name and email of course):

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     user.name James Chadwick
                     user.email james.chadwick@ess.eu

            If you don't, then you need to go to the \ `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__\  page and follow the instructions there. Note that we really want the output similar to the above, i.e. don't put a nickname or loginname instead of your full name, don't put upper case characters in the email, etc.

            .. rubric:: 3) Getting the framework
               :name: CodingFramework-3)Gettingtheframework

            Assuming your `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__ setup is already ready as discussed in the previous paragraph, the following command will download the framework repository:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git clone github:mctools/dgcode $HOME/dgcode_framework   # get the framework from GitHub

            .. rubric:: 4) Creating the projects directory with a bootstrap file in it
               :name: CodingFramework-4)Creatingtheprojectsdirectorywithabootstrapfileinit

            Building the code requires the framework's setup script to be run first, and a "projects" directory where your own code (project packages) is expected to be located. This directory will also be treated as the default location for the build output, and the final installation area, therefore you must define it even if you don't have any user packages yet, so only want to build the framework's code. You can define your projects directory by setting the *DGCODE_PROJECTS_DIR* environment variable. The intended and most practical way to set this variable – along with some other optional variables –, and also to call the framework's setup script, is by having a *bootstrap.sh* BASH script in the projects directory that can be run to initialte the whole setup process.

            If you are going to use one of the ESS Detector Group's shared repositories, such a *bootstrap.sh* script will be ready in it for you to use, so you continue by following the instructions in one of the 4a, 4b or 4c steps, depending on which repository your project's code will reside in. If you are a member or collaborator of the ESS Detector Group, we strongly encourage you to use the public `DGCode projects <https://github.com/ess-dg/dgcode_projects>`__ repository, but you should consider the recommendations in the `ESS Detector Group repositories <https://confluence.esss.lu.se/display/DGCODE/ESS+Detector+Group+repositories>`__ page to choose the most suitable one for your own purposes.

            -  If you're going to use the shared repository of **public** ESS Detector Group projects, follow the instructions in step 4a.
            -  If you're going to use the shared repository of **private** ESS Detector Group projects, follow the instructions in step 4b.
            -  If you're not a member or collaborator of the ESS Detector Group, and you're about to set up your own personal project directory (with your own repository, presumably), follow the instructions in step 4c.

            .. rubric:: 4a) Getting the DGCode Public Projects repository
               :name: CodingFramework-4a)GettingtheDGCodePublicProjectsrepository

            The `DGCode projects <https://github.com/ess-dg/dgcode_projects>`__ repository itself is meant to be used as a projects directory, therefore it already contains a `bootstrap.sh <https://github.com/ess-dg/dgcode_projects/blob/main/bootstrap.sh>`__ file that can be called to initiate the setup process. Assuming that you've cloned the framework to the suggested location ($HOME/dgcode_framework), the following commands should get you a local clone of the public projects repository, with a bootstrap.sh file in it ready to be used:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git clone github:ess-dg/dgcode_projects.git $HOME/dgcode_projects  # 1) get the public projects from GitHub
                     cd dgcode_projects/                                                # 2) step into the projects directory

            .. rubric:: 4b) Getting the DGCode Private Projects repository
               :name: CodingFramework-4b)GettingtheDGCodePrivateProjectsrepository

            The `DGCode Private Projects <https://git.esss.dk/dgcode/dgcode_private_projects>`__ repository itself is meant to be used as a projects directory, therefore it already contains a `bootstrap.sh <https://git.esss.dk/dgcode/dgcode_private_projects/-/blob/main/bootstrap.sh>`__ file that can be called to initiate the setup process. Assuming that you've cloned the framework to the suggested location ($HOME/dgcode_framework), the following commands should get you a local clone of the private projects repository, with a bootstrap.sh file in it ready to be used:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git clone gitlab:dgcode/dgcode_private_projects.git $HOME/dgcode_private_projects  # 1) get the private projects from GitLab
                     cd dgcode_private_projects/                                                        # 2) step into the projects directory

            .. rubric:: Note for 4a and 4b
               :name: CodingFramework-Notefor4aand4b

            Given that the bootstrap.sh file is version controlled in both shared repositories – and is therefore shared among the users –, you shouldn't edit it. This is because you might end up accidentally committing and pushing your changes to the repository, that would fill up this common file with you own personal configurations for everyone. What you should do instead – in case you want to use different configurations than the default ones in the bootstrap.sh file – is creating a file with the name "*bootstrap_extraconf.sh*" next to the bootstrap.sh file, and putting your commands to override the default configurations in it. This script file will be sourced by the bootstrap.sh file, so you still only have to use the "source bootstrap.sh" command in the next step to initiate the setup process. You don't have to worry about accidentally committing and pushing this \ *bootstrap_extraconf*\ .sh file to the repository, as it is added to the \ `gitignore <https://github.com/ess-dg/dgcode_projects/blob/main/.gitignore>`__\  file, and is therefore simply ignored by git.

            .. rubric:: 4c) Setting up a new projects directory
               :name: CodingFramework-4c)Settingupanewprojectsdirectory

            As mentioned earlier, the recommended way to set up the required environment variable, and to call the framework's setup script is by creating a *bootstrap.sh* BASH script in the projects directory, that can be run to trigger the setup process. Here is a template for such a bootstrap file that you can just copy and paste:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     #!/bin/bash

                     #Location where dgcode_framework is checked out (modify it if you use a
                     #different location):
                     DGCODE_FMWK_DIR="$HOME/dgcode_framework"

                     #Setup locations for where to keep your own project packages (the magic code
                     #below defaults this to being below the directory of this bootstrap file):
                     export DGCODE_PROJECTS_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

                     #Expert users might even want to override where to put build output or the final
                     #installation area (replace "auto" with an actual path if desired):
                     export DGCODE_INSTALL_DIR="auto"
                     export DGCODE_BUILD_DIR="auto"

                     #List paths to directories containing packages you want to be built along with
                     #the Framework and Project packages. (This may be useful for e.g., dependencies
                     #in large legacy repositories) 
                     export DGCODE_EXTRA_PKG_PATH=""

                     #Finish up by sourcing the main bootstrap.sh file from the dgcode framework:
                     . "$DGCODE_FMWK_DIR"/bootstrap.sh

            After setting the required *DGCODE_PROJECTS_DIR* variables – and the optional *DGCODE_INSTALL_DIR*, *DGCODE_BUILD_DIR* and *DGCODE_EXTRA_PKG_PATH* variables –, the bootstrap script above sources the setup file in the root directory of the framework (which is assumed to be located at $HOME/dgcode_framework), therefore the whole setup process required before building the code is triggered just by sourcing this short script in the projects directory.

            The following commands and instructions should help you to set up your projects directory and bootstrap file:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     mkdir my_dgcode_projects                   # 1) create a projects directory
                     cd my_dgcode_projects/                     # 2) step into the projects directory 
                     touch bootstrap.sh                         # 3) create an empty bootstrap.sh file
                     # 4) open the bootstrap.sh file with your preferred editor
                     # 5) copy and paste the bootstrap script template from above

            .. rubric:: 5) Building the code, and running the tests
               :name: CodingFramework-5)Buildingthecode,andrunningthetests

            Assuming that you've already stepped into your projects directory, the following commands are enough to build the code and run some basic tests:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     source bootstrap.sh       # 1) source the bootstrap.sh script to trigger the setup process
                     dgbuild -t                # 2) configure and build the code ("-t" means "and run the test jobs")

            If you are so lucky that you get a working installation right away, you should see something like:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     dgbuild: 
                     dgbuild: Successfully built and installed all enabled packages!
                     dgbuild: 
                     dgbuild: Summary:
                     dgbuild:   Framework directory              : /Users/mk/dgcode_framework/packages/Framework
                     dgbuild:   Projects directory               : /Users/mk/dgcode_projects
                     dgbuild:   Installation directory           : /Users/mk/dgcode_projects/install
                     dgbuild:   Build directory                  : /Users/mk/dgcode_projects/.bld
                     dgbuild:   Package search path              : /Users/mk/dgcode_framework/packages/Framework (53 built, 2 skipped)
                     dgbuild:                                      /Users/mk/dgcode_projects (0 built, 0 skipped)
                     dgbuild:   System                           : Darwin-19.6.0
                     dgbuild:   User configuration variables[*]  : ONLY='*'
                     dgbuild:   Required dependencies            : C[AppleClang/12.0.0] CMake[3.21.3] CXX[AppleClang/12.0.0]
                     dgbuild:                                      Python[3.9.7]
                     dgbuild:   Optional dependencies present    : DL[-] Fortran[GNU/11.2.0] Geant4[10.4.3]
                     dgbuild:                                      HDF5[1.12.1] Numpy[1.20.3] OSG[3.6.5] Threads[pthreads]
                     dgbuild:                                      ZLib[1.2.11]
                     dgbuild:   Optional dependencies missing[*] : Garfield ROOT
                     dgbuild:   53 packages built successfully   : Core DGBoost DMSCUtils DevTools EvtFile ExprParser
                     dgbuild:                                      G4CollectFilters G4CustomPyGen G4DataCollect
                     dgbuild:                                      G4ExprParser G4GeantinoInserter G4GravityHelper
                     dgbuild:                                      G4GriffGen G4HeatMap G4Interfaces G4Launcher
                     dgbuild:                                      G4MCPL G4MCPLPlugins G4Materials G4NCrystalRel
                     dgbuild:                                      ... (33 more, supply --verbose to see all)
                     dgbuild:   2 packages skipped due to [*]    : RootUtils SimpleHists2ROOT
                     dgbuild: 
                     dgbuild:  Running tests in /Users/mk/dgcode_projects/.bld/testresults:
                     dgbuild:  
                     dgbuild:   ---------------------------------------+-----------+--------+----------+------------------
                     dgbuild:    Test job results                      | Time [ms] | Job EC | Log-diff | Trouble info
                     dgbuild:   ---------------------------------------+-----------+--------+----------+------------------
                     dgbuild:    ess_pyana_test                        |    1399   |   OK   |    --    | --
                     dgbuild:   ---------------------------------------+-----------+--------+----------+------------------
                     dgbuild:  
                     dgbuild:    Test results are also summarised in dgtest_results_junitformat.xml
                     dgbuild:  
                     dgbuild:    All tests completed without failures!
                     dgbuild:  
                     dgbuild: You are all set to begin using the software!
                     dgbuild: 
                     dgbuild: To see available applications, type "ess_" and hit the TAB key twice.
                     dgbuild: 

            Note that the "-t" flag added to the dgbuild command was the reason it ran test jobs (successfully, in this case).

            When you log out and return to work the next time, you should only do this step, since the installed prerequisites, and the code is already there. Simply start with "source bootstrap.sh" in the projects directory each time. This is also the case when you open a new terminal window. Of course, you should frequently syncronise with the remote repository of your projects directory, and you might want to occasionally update your framework with "git pull" (or git fetch + git checkout FETCH_HEAD) as described on `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__, but that is another story.

            Tip for advanced users: If you create a bash file at $HOME/.dgcode_prebootstrap.sh then it will be sourced whenever you source bootstrap.sh, this might be useful in case you for instance have to source files in order to have access to certain externals such as Geant4 or ROOT but for some reason you do not wish to do this in your $HOME/.bashrc. Most users should not need this, however, as the dgdepfixer (described on `HowToInstallComputingPrereqs <https://confluence.esss.lu.se/display/DGCODE/HowToInstallComputingPrereqs>`__) will handles such issues.

            You might not be quite so lucky to have working installation at the first try, the next sections will go into various details about possible issues.

            .. rubric:: Failure at configuration stage - getting the right software installed
               :name: CodingFramework-Failureatconfigurationstage-gettingtherightsoftwareinstalled

            A few items are absolutely required in order to use the framework: C++ compiler, CMake, `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__ and Python3. How to install these will be highly dependent on your platform, so please refer to this separate wiki page for further instructions on this: `HowToInstallComputingPrereqs <https://confluence.esss.lu.se/display/DGCODE/HowToInstallComputingPrereqs>`__.

            .. rubric:: Some packages disabled due to missing Geant4, ROOT, Fortran, ...
               :name: CodingFramework-SomepackagesdisabledduetomissingGeant4,ROOT,Fortran,...

            To not have to force everyone to install all externals such as Geant4, ROOT, a Fortran compiler etc., those dependencies have been made optional. This means that if the configuration fails to detect the presence of one or more of these, it will simply disable packages who needs them and carry on with the rest.

            If our framework did not have this feature of optional external dependencies, then it would lead to annoying situations such as someone wanting to develop a program unrelated to Geant4 being forced to learn how to install Geant4. In the future we might add other optional dependencies as they are needed.

            .. rubric:: 6) Run validation tests
               :name: CodingFramework-6)Runvalidationtests

            The framework repository itself doesn't include many test scripts for efficiency reasons. To more thoroughly validate your setup, you can clone the `Validations <https://github.com/mctools/dgcode_val>`__ repository, that includes dedicated test packages. You can run these tests by adding the cloned directory to the packages search path with one of the optional environment variables before building:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git clone github:mctools/dgcode_val $HOME/dgcode_val                   # 1) get the validation packages from GitHub
                     export DGCODE_EXTRA_PKG_PATH="$DGCODE_EXTRA_PKG_PATH:$HOME/dgcode_val" # 2) add the directory to the package search path
                     dgbuild -t                                                             # 3) build the code and run the test jobs

            You could add the validation directory to the package search path in the *bootstrap.sh* file in the projects directory (or *bootstrap_extraconf*.sh if working in a shared repository) – in which case you would need to repeat the 'source bootstrap.sh' step before building the code –, however, leaving the file that way would cause the validations packages to be always included in the build&test process, which you might not want, unless you are developing the framework itself.

            .. rubric:: The dgbuild command
               :name: CodingFramework-Thedgbuildcommand

            Behind the scenes *dgbuild* uses CMake for configuration and subsequently GNU make for the actual build. Very importantly, dgbuild automatically detects whether or not the configuration step needs to be redone or if it can proceed automatically to the build step. All in all, this means that the developer will not have to worry at all about writing make files, redoing configuration, and so on.

            The dgbuild command has more options than just "-t" discussed above. Run "dgbuild -h" or "dgbuild --help" to see them all. A few of the more important ones are:

            -  -v or --verbose : Enable more verbosity during the build. Use this if you for instance wish to double-check which flags are passed on to linker or compiler.
            -  -jN or --jobs==N : specify number, N, of parallel processes used during build and test launches. By default dgbuild tries to make an educated best guess based on number of cores and level of activity on the system, so normally a developer will not have to use this flag at all. However, there is one notable exception which is the use-case of forcing the build to proceed in serial rather than parallel (i.e. "-j1"), which can be useful when debugging a compilation failure where the mixed output from different processes can look confusing.
            -  -d or --debug : Force DEBUG mode compilation (useful when bug-hunting: binaries contains debug symbols and `asserts <http://en.wikipedia.org/wiki/Assertion_%28computing%29>`__ are active).
            -  -r or --release : Force RELEASE mode compilation which is less useful during development, but might give significantly performance improvements.
            -  SOMEVAR=somevalue : Arguments of this form are passed directly to the CMake configuration.
            -  ROOT=0, Geant4=0 or Fortran=0 : Explicitly disable an optional dependency. This could be useful if the configuration picks up a badly installed version of ROOT or Geant4, or perhaps it picks up a very old Fortran compiler which is incompatible with our code.
            -  --all: Use to enable all packages. Enabling all packages is actually the default behaviour, however it is possible to change that (this option is discussed in the following section), so one can use this option to ensure that all packages are enabled (i.e. run "dgbuild --all --dt" to enable all packages and run all unit tests). Of course, packages which can't be enabled because you didn't install some optional dependency (like Geant4, ROOT, etc.) won't be enabled even when specifying --all.

            The exit code of the dgbuild command is 0 if and only if the build was successful.

            The dgbuild command can be invoked from within the framework or the projects directory (or any of their subdirectories).

            .. rubric:: Enabling packages
               :name: CodingFramework-Enablingpackages

            The default behaviour of the dgbuild command is trying to build all packages that can be found under the directories listed in the "package search path" printed in the build summary. The package search path constitutes of three parts, all of which is defined in the bootstrap.sh file in the projects directory:

            -  *DGCODE_FMWK_DIR/packages/Framework* - this part includes all the framework packages.
            -  *DGCODE_PROJECTS_DIR* - this part includes all packages under the projects directory (or any subdirectory).
            -  *DGCODE_EXTRA_PKG_PATH* - this part includes directories containing packages you want to be build along with the framework and projects packages. This may be useful for e.g., dependencies in large repositories.

            Packages found in these locations are by default enabled, unless you are missing some optional dependency (like Geant4, ROOT, etc.) that is required for the package to be built, in which case they will be disabled (and will be listed as such in the build summary). This means, that it is assumed that the user wants all packages under the projects directory (and the DGCODE_EXTRA_PKG_PATH) to be built.

            This assumption generally not true for users working with collective repositories with many possibly unrelated projects (e.g., the `DGCode projects <https://github.com/ess-dg/dgcode_projects>`__ and the `DGCode Private Projects <https://git.esss.dk/dgcode/dgcode_private_projects>`__), therefore this behaviour can be changed with the 'DGCODE_ENABLE_PROJECTS_PKG_SELECTION_FLAG' environment variable. Setting this variable true (or 1) will change the default package selection strategy to 'only enable framework packages, and packages in the DGCODE_EXTRA_PKG_PATH directories', and simultaneously enable the -p (or --project) dgbuild command option to selectively enable further packages:

            -  -p or --project=PROJECTNAME: Use when working with a given "project" (i.e. set of packages located in the same folder under dgcode_projects/PROJECTNAME). This makes sure you only build the relevant project packages, in addition to all of the packages under DGCODE_FMWK_DIR/packages/Framework, and under the directories listed in the *DGCODE_EXTRA_PKG_PATH.* (Behind the scenes this uses the variables ONLY and NOT, as described in the next section). If you do not want any project packages, just use "--project None".

            Note that in the `DGCode projects <https://github.com/ess-dg/dgcode_projects>`__ and the `DGCode Private Projects <https://git.esss.dk/dgcode/dgcode_private_projects>`__ repositories, the command:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     export DGCODE_ENABLE_PROJECTS_PKG_SELECTION_FLAG=true

            is added to the `bootstrap.sh <https://github.com/ess-dg/dgcode_projects/blob/main/bootstrap.sh>`__ file, so by default, users are expected to select the projects they want to build - avoiding the building of many unnecessary packages. 

            As a sidenote, if you are changing the value of the DGCODE_ENABLE_PROJECTS_PKG_SELECTION_FLAG for a projects directory that you've been already working with, it is safer to use the "dgbuild \ *--forget*\ " command to forget the stored configuration variables before invoking *dgbuild* again, just to be sure that you will be using the new configuration.

            .. rubric:: Enabling packages for advanced users
               :name: CodingFramework-Enablingpackagesforadvancedusers

            The --project (and the --all) option is actually a syntax sugar for the ONLY and NOT variables that enable fine package selection by handling multiple syntaxes to create an enabling or disabling filter for the package name or location. Each package (name or directory) will be matched against the patterns defined in the filter to decide if the package should be enabled or not. The value of the ONLY or NOT keyword should be a semicolon or comma separated list of patterns, using the following syntaxes:

            -  *Framework::TEXT* or *Projects::TEXT* or *Extra::TEXT* - the 'Framework::' or 'Projects::' part is replaced by the full path to the corresponding directory to create a pattern for the package directory. The same is done in case of 'Extra::', but multiple patterns might be created, one for all paths listed in the DGCODE_EXTRA_PKG_PATH (which might result in false positive matches). This syntax is intended for easy handling of relative paths.
            -  *TEXT* - if the pattern doesn't include '/', it is treated as a pattern for the package name. Note that it is possible to use wildcard '\*' character in this syntax (as well as in all other).
            -  */TEXT* -  a pattern starting with '/' is treated as absolute path, against which the package directories will be matched.
            -  *TEXT1/TEXT2* - if the pattern includes '/' but doesn't start with one, it is assumed to be a relative path. Not knowing exactly which path in the package search path it is relative to, all will be enabled, making false positive matches possible (e.g, DGCODE_FMWK_DIR/packages/Framework/TEXT1/TEXT2, DGCODE_PROJECTS_DIR/TEXT1/TEXT2, plus the same for all paths in the DGCODE_EXTRA_PKG_PATH)

            Examples:

            -  ONLY="Framework::\*"
            -  ONLY="Framework::\*,Extra::\*"
            -  ONLY="Framework::\*, Projects::\*"
            -  ONLY="Framework::\*;myFavoritePackage"
            -  ONLY="Framework::\*;/full/path/to/package;/full/path/to/other/package"
            -  NOT="packageWithAnoyingCompillationError"

            As a sidenote, --project=PROJECTNAME is actually turned into 'Projects::PROJECTNAME\*' behind the scenes.

            The dgrun command

            Very often a developer goes through repeated cycles of "rebuild and if all went well run this particular program". BASH-savvy users might come up with commands like the following to make their life easier:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     dgbuild > /dev/null && my_command arg1 arg2 arg3

            But even for BASH gurus, that is a lot of annoying typing, so we provide the "dgrun" command as well. Usage is simple, just put "dgrun " in front of the command you want to run, i.e.:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     dgrun my_command arg1 arg2 arg3

            Everything will then be automagic: configuration and rebuilding of all packages will take place when needed and *if* successful, the command "my_command arg1 arg2 arg3" will then be run.

            .. rubric:: Packages
               :name: CodingFramework-Packages

            Framework packages are located in the packages/Framework directory, or in a subdirectory of it. The name of the package is given by the name of the directory in which it is located, and at the very least it must contain one file called pkg.info, which in the first line contains information about which optional externals (ROOT, Geant4, Fortran, ...) the package needs and which other packages it depends on, if any. The latter is important for proper build order and link-time dependencies, so if for example PkgA depends on PkgB, then binaries and libraries in PkgA will be linked against the library (if any) from PkgB, and any public header files of PkgB will be available for inclusion in files in PkgA. In the following lines it can (should) provide brief description of the purpose of the package and information about who is the principal contact person for the package.

            Apart from the *pkg.info* file, everything else in a package is optional.

            .. rubric:: Format of the pkg.info file
               :name: CodingFramework-Formatofthepkg.infofile

            In the simplest case where a package does not depend on other packages, the contents of the pkg.info file will be very simple:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     package()

                     ##########################################################

                     Some short description of the package goes here.

                     primary author: some.person@someplace.com

            If the package depends on other packages, the name of those must be given after the keyword USEPKG inside the package(). So if for example the package for example depends on other packages named "SomeOtherPkg" and "AnotherPkg", the first line of pkg.info would look like:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     package(USEPKG SomeOtherPkg AnotherPkg)

            *Exception: All packages will implicitly depend on the package named* Core

            On the other hand, if the package needs one of the external optional dependencies (such as Geant4, ROOT, HDF5, Fortran, etc.), those are specified after a USEEXT keyword:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     package(USEEXT ROOT Fortran)

            Naturally, USEPKG and USEEXT can be combined:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     package(USEPKG CoolPackage Utils USEEXT Geant4)

            In this example, the package needs Geant4 and depends on two other packages, CoolPackage and Utils.

            To see a graphical representation of all packages and the dependencies between them, type "dgbuild --pkggraph" (requires the *dot* command from the *graphviz* bundle). To focus just on enabled pkgs, instead do "dgbuild --activegraph".

            Note that the author(s) of the code indicated in this file is to be contacted for proper acknowledgement in case the package is used to produce new scientific results.

            .. rubric:: Optional components of a package
               :name: CodingFramework-Optionalcomponentsofapackage

            A package with just a pkg.info file is not in itself very interesting. Obviously the package must provide something more, the possibilities for that are listed here.

            Note in general that we use the following convention for file formats:

            -  C++ : .hh (headers) .icc (inlines) .cc (source)
            -  C : .h (headers) .c (source)
            -  Fortran : .f
            -  Python : .py

            Even if you are used to using other extensions, it is important that you use the ones mentioned above, because otherwise the configuration and build mechanics will not work. Note that any directory is only allowed to contain files from one language.

            Note that the language format support is for C++17 and C code must be in C99 format. Also note that we use rather strict compilation flags allowing no warnings, etc.

            .. rubric:: C++/C header files
               :name: CodingFramework-C++/Cheaderfiles

            If your package needs to provide public header files, they must be created in a subdirectory of your package called **libinc/**. Any header file, e.g. MyHeaderFile.hh, placed here can be included from your own packages or from other packages depending on your package by:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     #include "PkgName/MyHeaderFile.hh"

            .. rubric:: C++/C libraries
               :name: CodingFramework-C++/Clibraries

            If your package needs to provide a library written in either C++ or C, you must create a subdirectory of your package called **libsrc/** and place any files there. It will obviously mean at least one source file (.cc or .c), but also any associated header files (unless users of your library need to be able to include them, in which case they go in libinc/.

            .. rubric:: C++/C/Fortran applications
               :name: CodingFramework-C++/C/Fortranapplications

            There is no limit to the number of compiled programs which can be provided by one package. Source and header files for each such program must be placed inside a directory whose name begins with "app\_" followed by a unique app name (unique within the package). To avoid clashes between applications in different packages, the final name of the binary will be prefixed with "ess\_<package name in lower case>\_<unique app name>". Thus, if files for an application is placed within a directory named "app_domystuff" in a package named MyPackage, then the actual name of the final program which can be launched by typing it at the command line will be "ess_mypackage_domystuff".

            Hint: After dgbuild is finished, you can type "ess" at the command line and then hit the TAB key to get a list of all resulting applications you can run (this also includes scripts, see below).

            In order to have a program run as an automatic test, then either the unique part of the name of the directory must start with "test" (i.e. the directory must be of the form app_testXXX/) or a reference log-file named test.log must be placed inside the directory (more about tests below).

            .. rubric:: Pure python modules
               :name: CodingFramework-Purepythonmodules

            Pure Python modules (\*.py) must be placed inside a subdirectory of the package named **python**. Each file will correspond to a submodule of a module with the same name as your package. In other words, if you in the package "MyPackage" place a file "mystuff.py" inside the "python/" subdirectory, then clients in the form of python scripts or other python (sub)modules can import your code by:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     import MyPackage.mystuff

            Note that if you do not provide an "\__init\_\_.py" file yourself, one will be created automatically.

            .. rubric:: Compiled python modules
               :name: CodingFramework-Compiledpythonmodules

            If you wish to have python modules written in C++ (either for efficiency or because you wish to make C++ functionality accessible to Python scripts), you must create sub directories named pycpp\_<modulename> Inside you must have at least one C++ source file in which you include Core/Python.hh and which contains a PYTHON_MODULE section. Here is a very basic example of how to make "somecppfunc" callable from python:

            | 

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: C++

                     #include "Core/Python.hh"
                     #include <iostream>

                     void somecppfunc()
                     {
                      std::cout<<"in somecppfunc in a python module"<<std::endl;
                     }

                     PYTHON_MODULE
                     {
                       py::def("somecppfunc", somecppfunc, "This is some C++ function");
                     }

            | 

            Each *pycpp\_<modulename>* sub directory will provide one python submodule. So if you for instance have a *pycpp_mymod/* subdir in a package MyPackage, then it will result in a python module loadable with:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     import MyPackage.mymod

            .. rubric:: Compiled \__init\_\_.py
               :name: CodingFramework-Compiled__init__.py

            Python does not as such support compiled \__init\_\_.py files, but it is possible to achieve the same effect by creating a compiled submodule named "\_init" and in \__init\_\_.py have a line:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     from _init import *

            This is automatically done by the dgcode framework if it has to create a \__init\_\_.py (i.e. none is provided by the developer) and there is a compiled module named "\_init" (i.e. in a subdir named "pycpp\__init" - notice the double underscore).

            .. rubric:: Scripts (normally Python or BASH)
               :name: CodingFramework-Scripts(normallyPythonorBASH)

            Of course, applications do not have to be compiled from C++, C or Fortran, but can equally well just be a script in for instance BASH or python. Simply place such scripts inside a subdirectory named **scripts/**. Make sure that any BASH script starts with the line:

            ``#!/bin/bash``

            and that any python scripts starts with (always refer to "python3" never just "python"):

            ``#!/usr/bin/env python3``

            As for compiled programs, any scripts will after installation be prefixed with ess\_<package name in lowercase>. Likewise, scripts can be marked as being a test by either prefixing their names with "test" or by placing a reference log file next to them: If the script is placed in a file **script/myscript** in the package MyPackage, then it will be able to be invoked after build by typing ess_mypackage_myscript and any test reference log file must be placed in **script/myscript.log**.

            .. rubric:: Data files
               :name: CodingFramework-Datafiles

            In addition to code in the form of programs, scripts, header files and python modules, packages can make any kind of data file accessible to programs by placing data files in the **data/** sub directory.

            This could for example be small data files to be used for input to various tests, but do note that Git repositories are **NOT** suitable for large files, especially not when binary. Thus, try to keep files in the data/ directory less than O(100 kilobytes).

            Data files will be available at a path given by: `$SBLD_DATA_DIR/<packagename>/<datafilename>`

            However, utilities are provided by the Core package for constructing such file paths from C++, python or BASH as the following examples of how to find the file 10evts_singleneutron_on_b10_full.griff from the package G4DataRead show:

            .. container:: code panel pdl

               .. container:: codeHeader panelHeader pdl

                  **Locating data files from C++**

               .. container:: codeContent panelContent pdl

                  .. code-block:: C++

                     #include "Core/FindData.hh"
                     ...
                     std::string datafile = Core::findData("G4DataRead","10evts_singleneutron_on_b10_full.griff");

            .. container:: code panel pdl

               .. container:: codeHeader panelHeader pdl

                  **Locating data files from python**

               .. container:: codeContent panelContent pdl

                  .. code-block:: python

                     import Core.FindData
                     datafile = Core.FindData("G4DataRead","10evts_singleneutron_on_b10_full.griff")

            .. container:: code panel pdl

               .. container:: codeHeader panelHeader pdl

                  **Locating data files from the command line**

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     DATAFILE=`ess_core_finddata G4DataRead 10evts_singleneutron_on_b10_full.griff`

            .. rubric:: Tests
               :name: CodingFramework-Tests

            As mentioned above, programs, either in the form of compiled C++/C/Fortran programs or Python/BASH scripts can be marked as "tests" and optionally reference log files can be provided. This serves the very important purpose on being able to validate the functionality of our code. This is super useful in at least two typical scenarios:

            #. After making changes to code, one can quickly validate that they did not break existing functionality. And if something was broken, tests are hopefully fine-grained enough that one immediately can figure out what went wrong.
            #. When installing the software on a new platform (i.e. a new flavour of Linux or OSX, or new versions of e.g. compilers, Geant4 or ROOT).

            Of course, for the above goals to be achieved, it is important to have a high test coverage. I.e. most packages should have one or two tests which very quickly can test the basic functionality provided by the package. It does not have to take a lot of time to develop a test, since most of the time you will anyway have created small scripts and programs during development of a package. Simply tidy them up a bit and mark them as a test.

            If you do **not** provide a test, then you can't really complain if someone else makes some changes which negatively influences the behaviour of your code. Their changes might after all have been done somewhere which seems to be unrelated, and they might not even have considered to double-check that your code still works afterwards. Heck, they might not even know the purpose of your code well enough to test it.

            In conclusion, tests ensure:

            -  Manpower savings
            -  Ability for many people to work together without friction
            -  Code of high quality
            -  Ability quickly validate installations on new platforms.

            Any application or script whose name (apart from the ess\_<packagename>\_ part) starts with "test" will be marked as a test, and so will any application or script who has a reference log-file provided (either a test.log file in the app_XXX/ directory or a scripts/myscript.log file for scripts/myscript). Tests consists of two parts: First of all, it must finish with an exit code of 0, and second of all those tests which have a reference log-file must give the same output as that given in the log-file. Thus, do not print out pointer addresses or absolute file-paths in a test with a reference log, since those will change spuriously between invocations and when the dgcode was checked out in different locations.

            For now, tests are required to complete in "a few seconds" only, because otherwise people would not run them. In the future, we could imagine open up a new category of "long-tests", if deemed necessary and useful.

            .. rubric:: Sharing your changes with other developers
               :name: CodingFramework-Sharingyourchangeswithotherdevelopers

            Once you have finished some changes to the code, like adding a new package with your code or making changes in existing packages, you should verify that everything works as expected by doing a "dgbuild -dt". If all goes well, you can commit your changes *in your local repository only* by doing (more on `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__):

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     dgbuild -dt (check that all tests are working)
                     git status  #shows affected files, see if you need to "git add" any, in order to stage them for your next commit.
                     git diff --cached# double check your changes, does it look like clean and tidy code?
                     git commit -m "a sensible comment in one line"

            Once in a while (it can be after one or after several commits) you should remember to actually push the changes to the central server:

            .. container:: code panel pdl

               .. container:: codeContent panelContent pdl

                  .. code-block:: sh

                     git push

            If you do not have write-permissions for the repository, send an email to `Thomas Kittelmann <https://confluence.esss.lu.se/display/~thomaskittelmann>`__. If the "git push" command fails, it might be because someone else added new code and you therefore first have to pull, merge and revalidate before committing and pushing once again (more on `Git <https://confluence.esss.lu.se/display/DGCODE/Git>`__).
