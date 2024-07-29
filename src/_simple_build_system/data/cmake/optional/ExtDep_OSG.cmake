set(HAS_OSG 0)

#Reconfigure when location of osgversion programme changed:
set(autoreconf_bin_OSG "osgversion")
#Or when one of these vars changed:
set(autoreconf_env_OSG "OSGDIR;OSG_DIR;OSG_ROOT")

if (NOT SBLD_VERBOSE)
  set(OpenSceneGraph_FIND_QUIETLY ON)
endif()

find_package(OpenSceneGraph 3.2.0 COMPONENTS osgDB osgUtil osgViewer osgGA osgFX osgText)
if (OPENSCENEGRAPH_FOUND)
  set(HAS_OSG 1)
  findpackage_liblist_to_flags("${OPENSCENEGRAPH_LIBRARIES}" "" ExtDep_OSG_LINK_FLAGS)
  set(ExtDep_OSG_COMPILE_FLAGS "-I${OPENSCENEGRAPH_INCLUDE_DIRS}")
  set(ExtDep_OSG_VERSION "${OPENSCENEGRAPH_VERSION}")
  if( DEFINED ENV{CONDA_PREFIX} AND NOT APPLE )
    #See comments in ExtDep_Geant4.cmake for comments about this hack.
    file(REAL_PATH "${OPENSCENEGRAPH_INCLUDE_DIRS}" real_osgincdir)
    file(REAL_PATH $ENV{CONDA_PREFIX} real_condaprefix)
    cmake_path(IS_PREFIX real_condaprefix "${real_osgincdir}" NORMALIZE tmp)
    if (tmp)
      include(CheckLinkerFlag)
      check_linker_flag(CXX -Wl,--allow-shlib-undefined tmp)
      if ( tmp )
        #include/osg/Vec3f
        message( STATUS "OSG from conda detected: Adding -Wl,--allow-shlib-undefined to work around missing symbols.")
        set(ExtDep_OSG_LINK_FLAGS "${ExtDep_OSG_LINK_FLAGS} -Wl,--allow-shlib-undefined")
      endif()
    endif()
  endif()
endif()
