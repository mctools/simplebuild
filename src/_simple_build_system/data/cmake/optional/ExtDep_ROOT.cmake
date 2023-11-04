
# We set everything up through the root-config script. The script is looked for
# in three ways (in order of preference):
#
# 1) If ROOT_DIR is set to a directory look for ROOT_DIR/bin/root-config
# 2) If ROOTSYS is set to a directory look for ROOTSYS/bin/root-config
# 3) Look for root-config in PATH
#
# Everything is then based on root-config "--noauxcflags --cflags", "--noauxlibs --libs" and "--has-python"/"--has-gdml".
#
# Results:
#   Sets HAS_ROOT, ExtDep_ROOT_COMPILE_FLAGS and ExtDep_ROOT_LINK_FLAGS
#   ExtDep_ROOT_COMPILE_FLAGS will contain -DHAS_ROOT_GDML if GDML module is present.
#   ExtDep_ROOT_COMPILE_FLAGS will contain -DHAS_ROOT_PYTHON if PYTHON module is present.

set(HAS_ROOT 0)

#Reconfigure when location of root-config script changed or value of ROOTSYS env. variable changed.
set(autoreconf_bin_ROOT "root-config")
set(autoreconf_env_ROOT "ROOTSYS")

set(root_config_file "NOTFOUND")
if (ROOT_DIR AND EXISTS "${ROOT_DIR}/bin/root-config")
  set(root_config_file "${ROOT_DIR}/bin/root-config")
elseif (NOT "x$ENV{ROOTSYS}" STREQUAL "x" AND EXISTS "$ENV{ROOTSYS}/bin/root-config")
  set(root_config_file "$ENV{ROOTSYS}/bin/root-config")
else()
  find_path(root_config_path root-config PATHS ENV PATH)
  if (EXISTS "${root_config_path}/root-config")
    set(root_config_file "${root_config_path}/root-config")
  endif()
endif()

if (root_config_file)
  message( STATUS "Base ROOT setup on ${root_config_file}")
  #We require that ROOT was build with C++17 or later (c++17 aka c++1z, c++20 aka c++2a, ...):
  execute_process(COMMAND "${root_config_file}" "--cflags" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  if (NOT tmp MATCHES "-std=c\\+\\+1z" AND NOT tmp MATCHES "-std=c\\+\\+17" AND NOT tmp MATCHES "-std=c\\+\\+2a" AND NOT tmp MATCHES "-std=c\\+\\+20")
    message( STATUS "Warning: The ROOT installation was not built with C++17 support and can not be used.")
    set(root_config_file "NO")
  endif()
endif()

if (root_config_file)
  set(HAS_ROOT 1)
  execute_process(COMMAND "${root_config_file}" "--noauxlibs" "--libs" OUTPUT_VARIABLE ExtDep_ROOT_LINK_FLAGS OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${ExtDep_ROOT_LINK_FLAGS}" ExtDep_ROOT_LINK_FLAGS)
  execute_process(COMMAND "${root_config_file}" "--noauxcflags" "--cflags" OUTPUT_VARIABLE ExtDep_ROOT_COMPILE_FLAGS OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${ExtDep_ROOT_COMPILE_FLAGS}" ExtDep_ROOT_COMPILE_FLAGS)
  execute_process(COMMAND "${root_config_file}" "--cflags" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  #OLD # #C++14 support might have to be enabled, since ROOT headers rely on features only in c++14 (if available at ROOT build time - our root install script should disable it).
  #OLD # if (tmp MATCHES "-std=c\\+\\+1y")
  #OLD #   set(ExtDep_ROOT_COMPILE_FLAGS "${ExtDep_ROOT_COMPILE_FLAGS} -std=c++1y")
  #OLD # elseif (tmp MATCHES "-std=c\\+\\+14")
  #OLD #   set(ExtDep_ROOT_COMPILE_FLAGS "${ExtDep_ROOT_COMPILE_FLAGS} -std=c++14")
  #OLD # endif()
  execute_process(COMMAND "${root_config_file}" "--has-gdml" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  if ( NOT "x${tmp}" STREQUAL "xyes" )
    message( STATUS "Warning: ROOT does not have GDML enabled.")
    set(HAS_ROOT_GDML 0)
  else()
    set(ExtDep_ROOT_COMPILE_FLAGS "${ExtDep_ROOT_COMPILE_FLAGS} -DHAS_ROOT_GDML")
    set(HAS_ROOT_GDML 1)
  endif()
  #NB was --has-python before 6.22
  execute_process(COMMAND "${root_config_file}" "--has-pyroot" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  if ( NOT "x${tmp}" STREQUAL "xyes" )
    message( STATUS "Warning: ROOT does not have Python enabled (NOTE: This now requires root 6.22 or later!).")
    set(HAS_ROOT_PYTHON 0)
  else()
    set(HAS_ROOT_PYTHON 1)
    execute_process(COMMAND "${Python_EXECUTABLE}" "-c" "import ROOT;ROOT.TH1F('bla','bla',10,0.0,1.0)" OUTPUT_QUIET RESULT_VARIABLE tmp_ec ERROR_QUIET)
    if (NOT "x${tmp_ec}" STREQUAL "x0")
      message( STATUS "Warning: ROOT has Python enabled but 'import ROOT' fails (likely it was compiled against a wrong Python installation or against Python2 instead of Python3).")
      set(HAS_ROOT_PYTHON 0)
    endif()
  endif()
  if (HAS_ROOT_PYTHON STREQUAL "1")
    set(ExtDep_ROOT_COMPILE_FLAGS "${ExtDep_ROOT_COMPILE_FLAGS} -DHAS_ROOT_PYTHON")
    #NB was --lPyROOT before 6.22
    set(ExtDep_ROOT_LINK_FLAGS "${ExtDep_ROOT_LINK_FLAGS} -lROOTTPython")
  endif()
  execute_process(COMMAND "${root_config_file}" "--has-geom" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  if ( NOT "x${tmp}" STREQUAL "xyes" )
    #Might not be installed, but at least on Fedora 19 this might be wrong so we
    #check for the library as well.
    execute_process(COMMAND "${root_config_file}" "--libdir" OUTPUT_VARIABLE tmp2 OUTPUT_STRIP_TRAILING_WHITESPACE)
    string(STRIP "${tmp2}" tmp2)
    if (EXISTS "${tmp2}/libGeom.so")
      set(tmp yes)
    endif()
  endif()
  if ( NOT "x${tmp}" STREQUAL "xyes" )
    message( STATUS "Warning: ROOT does not have Geom enabled.")
    set(HAS_ROOT_GEOM 0)
  else()
    set(HAS_ROOT_GEOM 1)
    set(ExtDep_ROOT_COMPILE_FLAGS "${ExtDep_ROOT_COMPILE_FLAGS} -DHAS_ROOT_Geom")
    set(ExtDep_ROOT_LINK_FLAGS "${ExtDep_ROOT_LINK_FLAGS} -lGeom")#note that root-config does not add -lGeom by itself.
  endif()
  #version:
  execute_process(COMMAND "${root_config_file}" "--version" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  set(ExtDep_ROOT_VERSION "${tmp}")
endif()
