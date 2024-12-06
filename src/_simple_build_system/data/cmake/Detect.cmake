######################################################
###   Standard packages which we always require    ###
###   => all code can implicitly depend on these   ###
######################################################

cmake_policy(PUSH)
include("ExtDep_Python.cmake")
cmake_policy(POP)

include("ExtractFlags.cmake")

cmake_policy(PUSH)
include("ExtDep_pybind11.cmake")
cmake_policy(POP)

#Declare include dirs added above as -isystem (and remove /usr/include):
declare_includes_as_system_headers(SBLD_GLOBAL_COMPILE_FLAGS_CXX)
declare_includes_as_system_headers(SBLD_GLOBAL_COMPILE_FLAGS_C)

#####################################################################
###   Optional dependencies which if absent causes parts of our   ###
###   code to not be built and which the developer of each        ###
###   package must explicitly add as a dependency if needed       ###
#####################################################################

#Create extdep list based on files in optional:
set(extdep_dirs "${CMAKE_CURRENT_LIST_DIR}/optional")
FILE(GLOB extdepfiles "${extdep_dirs}/ExtDep_*.cmake")

if( DEFINED SBLD_EXTRA_EXTDEP_PATH )
  #Add extra files in downstream projects:
  foreach( tmp_extra_dir ${SBLD_EXTRA_EXTDEP_PATH} )
    #list( APPEND extdep_dirs ${tmp_extra_dir} )
    FILE(GLOB tmp_extra_files "${tmp_extra_dir}/ExtDep_*.cmake")
    foreach( tmp_extra_file ${tmp_extra_files} )
      message(STATUS "Using custom dependency file: ${tmp_extra_file}")
      list(APPEND extdepfiles "${tmp_extra_file}")
      if ( NOT "${tmp_extra_dir}" IN_LIST extdep_dirs )
        list(APPEND extdep_dirs  "${tmp_extra_dir}")
      endif()
    endforeach()
  endforeach()
endif()

set(extdep_all "")
foreach(extdepfile ${extdepfiles})
  GET_FILENAME_COMPONENT(extdepfile "${extdepfile}" NAME)
  string(LENGTH ${extdepfile} tmp)
  MATH(EXPR tmp "${tmp}-13")
  string(SUBSTRING ${extdepfile} 7 ${tmp} extdepfile)
  if ( "${extdepfile}" IN_LIST extdep_all )
    message(FATAL_ERROR "Name of custom dependency clashes with existing definition: ${extdepfile}" )
  endif()
  list(APPEND extdep_all "${extdepfile}")
endforeach()
list(SORT extdep_all)

#Go through and treat each in turn:
set(extdep_present "")
set(extdep_missing "")
set(extdep_autoreconf_bin_list "cmake;gcc;g++;clang;clang++;python3")
set(extdep_autoreconf_env_list "CC;CXX;DGDEPDIR;PYTHONHOME;VIRTUAL_ENV;SDKROOT;CPATH")
set(extdep_pending "${extdep_all}")

foreach(extdep ${extdep_all})
    set(HAS_${extdep} "pending")
endforeach()

string(REPLACE ":" ";" SBLD_ACTUALLY_USED_EXTDEPS "${SBLD_ACTUALLY_USED_EXTDEPS}")

#Make sure the SBLD_ACTUALLY_USED_EXTDEPS are first in the list, since they might
#activate other not directly used extdeps via the EXTDEPS_WAITS_FOR variable
#(e.g. Garfield might activate ROOT):
foreach( tmp ${SBLD_ACTUALLY_USED_EXTDEPS} )
  if ( NOT "${tmp}" IN_LIST extdep_pending )
    message( FATAL_ERROR "Unknown external dependency specified in pkg.info file: \"${tmp}\"" )
  endif()
  list(REMOVE_ITEM extdep_pending ${tmp})
endforeach()
list( PREPEND extdep_pending ${SBLD_ACTUALLY_USED_EXTDEPS} )

set( SBLD_SKIPPED_UNUSED_DEPS "" )
while(extdep_pending)
  list(GET extdep_pending 0 extdep)

  #We can explicitly ignore a dependency named SomeExtdep by putting "SomeExtdep=0" or "SomeExtdep=OFF", etc.
  if ( NOT "x${${extdep}}" STREQUAL "x"  AND NOT "${${extdep}}" )
    set(HAS_${extdep} 0)
    message( STATUS "Skipping since this dependency was explicitly disabled")
  elseif( NOT "${extdep}" IN_LIST SBLD_ACTUALLY_USED_EXTDEPS )
    set(HAS_${extdep} 0)
    #message( STATUS "Skipping since no active packages require this dependency")
    list( APPEND "SBLD_SKIPPED_UNUSED_DEPS" "${extdep}" )
  else()
    cmake_policy(PUSH)
    set( EXTDEPS_WAITS_FOR "")
    message( STATUS "Checking for ${extdep} installation")
    set( tmp_found "OFF" )
    foreach( tmpdir ${extdep_dirs} )
      set( tmp_candidate "${tmpdir}/ExtDep_${extdep}.cmake" )
      if ( EXISTS "${tmp_candidate}" )
        if ( tmp_found )
          message(
            FATAL_ERROR "Internal inconsistency when searching extdep dirs"
            " (found ${extdep} more than once)"
          )
        endif()
        set( tmp_found "ON" )
        include("${tmp_candidate}")
      endif()
    endforeach()
    if (NOT tmp_found )
      message(
        FATAL_ERROR "Internal inconsistency when searching extdep dirs"
        " (could not find ${extdep} again)")
    endif()
    if ( EXTDEPS_WAITS_FOR )
      list( APPEND SBLD_ACTUALLY_USED_EXTDEPS ${EXTDEPS_WAITS_FOR} )
    endif()
    cmake_policy(POP)
  endif()

  if ("x${HAS_${extdep}}" STREQUAL "xpending")
    message( STATUS "Checking for ${extdep} installation -- postponed")
    list(REMOVE_ITEM extdep_pending ${extdep})
    list(APPEND extdep_pending ${extdep})
  else()
    if (NOT "x${HAS_${extdep}}" STREQUAL "x0" AND NOT "x${HAS_${extdep}}" STREQUAL "x1")
      message( FATAL_ERROR "Inconsistency in definition of external dependency ${extdep}")
    endif()

    list(APPEND extdep_autoreconf_bin_list ${autoreconf_bin_${extdep}})

    list(APPEND extdep_autoreconf_env_list ${autoreconf_env_${extdep}})

    if (HAS_${extdep})
      list(APPEND extdep_present ${extdep})
      #Declare extdeps as system headers, unless it requests otherwise:
      if ( NOT DEFINED ExtDep_${extdep}_IsNotSystemHeaders )
        declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS)
        declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS_C)
        declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS_CXX)
      endif()
      if (ExtDep_${extdep}_COMPILE_FLAGS)
        if (ExtDep_${extdep}_COMPILE_FLAGS_C OR ExtDep_${extdep}_COMPILE_FLAGS_CXX)
          message(FATAL_ERROR "Inconsistency in definition of external dependency ${extdep} (should set either _COMPILE_C+_COMPILE_CXX or just _COMPILE)")
        endif()
        #Copy all flags - but keep those specific to C++ from being applied for C:
        set(ExtDep_${extdep}_COMPILE_FLAGS_CXX "${ExtDep_${extdep}_COMPILE_FLAGS}")
        string(REPLACE " " ";" tmplist "${ExtDep_${extdep}_COMPILE_FLAGS}")
        #set(tmplist "${ExtDep_${extdep}_COMPILE_FLAGS}")#convert from "a b c" to actual list of a b c
        foreach(tmpflag ${tmplist})
          if (NOT tmpflag MATCHES "-W.*-virtual")#FIXME: Also --std=c++ ?
            set(ExtDep_${extdep}_COMPILE_FLAGS_C "${ExtDep_${extdep}_COMPILE_FLAGS_C} ${tmpflag}")
          endif()
        endforeach()
      endif()
      set(ExtDep_${extdep}_COMPILE_FLAGS "")
      message( STATUS "Checking for ${extdep} installation -- yes")
      message( STATUS "Found ${extdep} version: ${ExtDep_${extdep}_VERSION}")
      if (SBLD_VERBOSE)
        message( STATUS "${extdep} link flags: ${ExtDep_${extdep}_LINK_FLAGS}")
        message( STATUS "${extdep} compile flags (C++ only): ${ExtDep_${extdep}_COMPILE_FLAGS_CXX}")
        message( STATUS "${extdep} compile flags (C/others): ${ExtDep_${extdep}_COMPILE_FLAGS_C}")
      endif()
    else()
      list(APPEND extdep_missing ${extdep})
      if( "${extdep}" IN_LIST SBLD_ACTUALLY_USED_EXTDEPS )
        message( STATUS "Checking for ${extdep} installation -- no")
      endif()
    endif()

    list(REMOVE_ITEM extdep_pending ${extdep})
  endif()
endwhile()

if (SBLD_SKIPPED_UNUSED_DEPS)
  set( tmpnperline 6 )
  set( tmpfirst 1 )
  while( SBLD_SKIPPED_UNUSED_DEPS )
    list( LENGTH SBLD_SKIPPED_UNUSED_DEPS tmpn )
    list( SUBLIST SBLD_SKIPPED_UNUSED_DEPS 0 ${tmpnperline} tmp )
    if ( tmpn GREATER ${tmpnperline} )
      list( SUBLIST SBLD_SKIPPED_UNUSED_DEPS ${tmpnperline} 9999 SBLD_SKIPPED_UNUSED_DEPS )
    else()
      set( SBLD_SKIPPED_UNUSED_DEPS "" )
    endif()
    string( REPLACE ";" " " tmp "${tmp}")
    if ( tmpfirst EQUAL 1 )
      message( STATUS "Skipped unused dependencies: ${tmp}" )
    else()
      message( STATUS "                             ${tmp}" )
    endif()
    set( tmpfirst 0 )
  endwhile()
endif()
