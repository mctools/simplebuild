
# Although Geant4 provides a cmake script to source, the quality is a bit
# sub-standard. For consistency we thus set everything up via the geant4-config
# script. The script is looked for in three ways (in order of preference):
#
# 1) If Geant4_DIR is set to a directory look for Geant4_DIR/bin/geant4-config
# 2) If G4INSTALL is set to a directory look for G4INSTALL/bin/geant4-config
# 3) Look for geant4-config in PATH
#
# Everything is then based on geant4-config "--cflags", "--libs" and "--has-feature gdml".
#
# Results:
#   Sets HAS_Geant4, ExtDep_Geant4_COMPILE_FLAGS_CXX and ExtDep_Geant4_LINK_FLAGS
#   ExtDep_Geant4_COMPILE_FLAGS_CXX will contain -DHAS_Geant4_GDML if GDML module is present.
#   ExtDep_Geant4_COMPILE_FLAGS_C is left empty, so we are assuming C code does
#   not need Geant4 headers.

# TODO: Deal with g4py and data files.

set(HAS_Geant4 0)

#Reconfigure when location of geant4-config script changed or value of G4INSTALL env. variable changed.
set(autoreconf_bin_Geant4 "geant4-config")
set(autoreconf_env_Geant4 "G4INSTALL")

set(geant4_config_file "NOTFOUND")
if (Geant4_DIR AND EXISTS "${Geant4_DIR}/bin/geant4-config")
  set(geant4_config_file "${Geant4_DIR}/bin/geant4-config")
elseif (NOT "x$ENV{G4INSTALL}" STREQUAL "x" AND EXISTS "$ENV{G4INSTALL}/bin/geant4-config")
  set(geant4_config_file "$ENV{G4INSTALL}/bin/geant4-config")
else()
  find_path(geant4_config_path geant4-config PATHS ENV PATH)
  if (EXISTS "${geant4_config_path}/geant4-config")
    set(geant4_config_file "${geant4_config_path}/geant4-config")
  endif()
endif()

if (geant4_config_file)
  set(HAS_Geant4 1)
  message( STATUS "Base Geant4 setup on ${geant4_config_file}")
  execute_process(COMMAND "${geant4_config_file}" "--libs" OUTPUT_VARIABLE ExtDep_Geant4_LINK_FLAGS OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${ExtDep_Geant4_LINK_FLAGS}" ExtDep_Geant4_LINK_FLAGS)
  execute_process(COMMAND "${geant4_config_file}" "--cflags" OUTPUT_VARIABLE ExtDep_Geant4_COMPILE_FLAGS_CXX OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${ExtDep_Geant4_COMPILE_FLAGS_CXX}" ExtDep_Geant4_COMPILE_FLAGS_CXX)
  execute_process(COMMAND "${geant4_config_file}" "--has-feature" "gdml" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  if ( NOT "x${tmp}" STREQUAL "xyes" )
    message( STATUS "Warning: Geant4 does not have GDML enabled.")
  else()
    #Finally, if G4 was compiled with GDML support we need to explicitly add
    #xercesc as a dependency.
    find_package(XercesC)
    if ( NOT XercesC_FOUND )
      message( STATUS "Warning: Geant4 has GDML enabled but XercesC could not be detected! Will pretend Geant4-GDML is absent.")
    else()
      #assuming only one entry in XercesC_INCLUDE_DIRS:
      set(ExtDep_Geant4_COMPILE_FLAGS_CXX "${ExtDep_Geant4_COMPILE_FLAGS_CXX} -I${XercesC_INCLUDE_DIRS} -isystem${XercesC_INCLUDE_DIRS} -DHAS_Geant4_GDML")
      findpackage_liblist_to_flags("${XercesC_LIBRARIES}" "" tmp)
      set(ExtDep_Geant4_LINK_FLAGS "${ExtDep_Geant4_LINK_FLAGS} ${tmp}")
    endif()
  endif()
  #Make sure G4 does not overrule the standard:
  strip_cpp_version_flags( ExtDep_Geant4_COMPILE_FLAGS_CXX )
  #version:
  execute_process(COMMAND "${geant4_config_file}" "--version" OUTPUT_VARIABLE tmp OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(STRIP "${tmp}" tmp)
  set(ExtDep_Geant4_VERSION "${tmp}")

  #Leave C flags empty, Geant4 is for C++ only:
  set(ExtDep_Geant4_COMPILE_FLAGS_C "")

  if( DEFINED ENV{CONDA_PREFIX} AND NOT APPLE )
    #Sadly, it seems on at least ubuntu 20.04 on August 7 2023, geant4 in
    #conda-forge has unresolved but unused symbols (possible memcpy@GLIBC2.17
    #and two others, through the Qt dependency). So if CONDA_PREFIX is set, and
    #Geant4 comes from conda, we add -Wl,--allow-shlib-undefined, although
    #normally we would really try to avoid that.
    #
    # NOTE: We also have this workaround in other extdeps (e.g. OSG, HDF5), so
    # any updates here should be reflected there as well.
    file(REAL_PATH ${geant4_config_file} real_g4cfg)
    file(REAL_PATH $ENV{CONDA_PREFIX} real_condaprefix)
    cmake_path(IS_PREFIX real_condaprefix "${real_g4cfg}" NORMALIZE tmp)
    if (tmp)
      include(CheckLinkerFlag)
      check_linker_flag(CXX -Wl,--allow-shlib-undefined tmp)
      if ( tmp )
        message( STATUS "Geant4 from conda detected: Adding -Wl,--allow-shlib-undefined to work around missing symbols.")
        set(ExtDep_Geant4_LINK_FLAGS "${ExtDep_Geant4_LINK_FLAGS} -Wl,--allow-shlib-undefined")
        #NB: we could in principle also do a try_compile first perhaps and see if
        #this is still needed (and works), but it is complicated to replicate here
        #the exact compilation command that simplebuild will create later, since some
        #flags might be added elsewhere.
      endif()
    endif()
  endif()
endif()
