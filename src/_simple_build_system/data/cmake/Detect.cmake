######################################################
###   Standard packages which we always require    ###
###   => all code can implicitly depend on these   ###
######################################################

cmake_policy(PUSH)
include("ExtDep_Python.cmake")
cmake_policy(POP)

include( "ExtractFlags.cmake")

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

#Create extdep_all list based on files in optional:
FILE(GLOB extdepfiles "optional/ExtDep_*.cmake")
set(extdep_all "")
foreach(extdepfile ${extdepfiles})
  GET_FILENAME_COMPONENT(extdepfile ${extdepfile} NAME)
  string(LENGTH ${extdepfile} tmp)
  MATH(EXPR tmp "${tmp}-13")
  string(SUBSTRING ${extdepfile} 7 ${tmp} extdepfile)
  list(APPEND extdep_all ${extdepfile})
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

while(extdep_pending)
  list(GET extdep_pending 0 extdep)

  message( STATUS "Checking for ${extdep} installation")
  #We can explicitly ignore a dependency named SomeExtdep by putting "SomeExtdep=0" or "SomeExtdep=OFF", etc.
  if ( NOT "x${${extdep}}" STREQUAL "x"  AND NOT "${${extdep}}" )
    set(HAS_${extdep} 0)
    message( STATUS "Skipping since this dependency was explicitly disabled")
  elseif( NOT "${extdep}" IN_LIST SBLD_ACTUALLY_USED_EXTDEPS )
    set(HAS_${extdep} 0)
    message( STATUS "Skipping since no active packages require this dependency")
  else()
    cmake_policy(PUSH)
    set( EXTDEPS_WAITS_FOR "")
    include(optional/ExtDep_${extdep}.cmake)
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
      declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS)
      declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS_C)
      declare_includes_as_system_headers(ExtDep_${extdep}_COMPILE_FLAGS_CXX)
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
      message( STATUS "Checking for ${extdep} installation -- no")
    endif()

    list(REMOVE_ITEM extdep_pending ${extdep})
  endif()
endwhile()
