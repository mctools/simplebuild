cmake_minimum_required(VERSION 3.24.2...3.31)

if (SBLD_QUIET)
  #override normal message function and block anything except errors and warnings
  function(message)
    list(GET ARGV 0 MessageType)
    if(MessageType STREQUAL "FATAL_ERROR" OR
        MessageType STREQUAL "SEND_ERROR" OR
        MessageType STREQUAL "WARNING" OR
        MessageType STREQUAL "AUTHOR_WARNING" )
      list(REMOVE_AT ARGV 0)
      _message(${MessageType} "${ARGV}")
    endif()
  endfunction()
endif()

if( NOT CMAKE_BUILD_TYPE )
  message( FATAL_ERROR "CMAKE_BUILD_TYPE should always be set" )
endif()

if (NOT "${CMAKE_BUILD_TYPE}" MATCHES "^(Debug|Release)$")
  message( FATAL_ERROR "For simplicity we require CMAKE_BUILD_TYPE to be exactly Debug or Release." )
endif()

message( STATUS "Using CMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}" )

project( DETECT LANGUAGES C CXX )

set(output_filename "cmakecfg.txt")

set(BUILD_SHARED_LIBS ON)

if ( NOT DEFINED SBLD_RELDBG_MODE )
  set(SBLD_RELDBG_MODE OFF)
endif()

#We compile with -pedantic and -Werror unless SBLD_RELAX is set:
set(FLAG_PEDANTIC "")
set(FLAG_WERROR "")
if (NOT SBLD_RELAX)
  set(FLAG_PEDANTIC "-pedantic ")
  set(FLAG_WERROR "-Werror ")
endif()

set(FLAGS_PLATFORM_C "")
set(FLAGS_PLATFORM_CXX "")
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  if (CMAKE_CXX_COMPILER_VERSION VERSION_GREATER 6.99)
    #allow "define private public" for now
    set(FLAGS_PLATFORM_CXX " -Wno-reserved-id-macro -Wno-keyword-macro")
  endif()
endif()

set(SBLD_GLOBAL_COMPILE_FLAGS_CXX "${FLAG_PEDANTIC}-std=c++17 -Wextra ${FLAG_WERROR}-Wall -Woverloaded-virtual -Wno-non-virtual-dtor -Wno-long-long -Wwrite-strings -Wpointer-arith -Wno-variadic-macros -Wshadow${FLAGS_PLATFORM_CXX} ${SBLD_EXTRA_CFLAGS}")
set(SBLD_GLOBAL_COMPILE_FLAGS_C "${FLAG_PEDANTIC}-std=c99 -Wextra${FLAGS_PLATFORM_C} ${FLAG_WERROR}-Wall ${SBLD_EXTRA_CFLAGS}")

set(SBLD_GLOBAL_COMPILE_FLAGS_Fortran "")
set(SBLD_GLOBAL_LINK_FLAGS "${SBLD_EXTRA_LDFLAGS}")
set(SBLD_GLOBAL_LINK_FLAGS_PREPENDED "")
if ("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
  #Ubuntu has --as-needed by default and GCC, so we overrule this (prepended, before specific libs appear on the link cmd):
  set(SBLD_GLOBAL_LINK_FLAGS_PREPENDED "-Wl,--no-as-needed")
  #With GCC we can (since v4.6) make sure the compiler stops after after a few
  #errors, which is a bit more friendly for most users:
  set(SBLD_GLOBAL_COMPILE_FLAGS_CXX "${SBLD_GLOBAL_COMPILE_FLAGS_CXX} -fmax-errors=3")
  set(SBLD_GLOBAL_COMPILE_FLAGS_C "${SBLD_GLOBAL_COMPILE_FLAGS_C} -fmax-errors=3")
endif()

if ( APPLE AND DEFINED CMAKE_OSX_SYSROOT AND NOT "x${CMAKE_OSX_SYSROOT}" STREQUAL "x" )
  set(SBLD_GLOBAL_COMPILE_FLAGS_C "${SBLD_GLOBAL_COMPILE_FLAGS_C} -isysroot ${CMAKE_OSX_SYSROOT}")
  set(SBLD_GLOBAL_COMPILE_FLAGS_CXX "${SBLD_GLOBAL_COMPILE_FLAGS_CXX} -isysroot ${CMAKE_OSX_SYSROOT}")
  set(SBLD_GLOBAL_COMPILE_FLAGS_Fortran "${SBLD_GLOBAL_COMPILE_FLAGS_Fortran} -isysroot ${CMAKE_OSX_SYSROOT}")
  set(SBLD_GLOBAL_LINK_FLAGS "${SBLD_GLOBAL_LINK_FLAGS} -isysroot ${CMAKE_OSX_SYSROOT}")
endif()

if ( "x${CMAKE_CXX_COMPILER_ID}" STREQUAL "xIntelLLVM" )
  set( SBLD_ISINTEL "ON" )
else()
  set( SBLD_ISINTEL "OFF" )
endif()

set( sbld_extra_ccxx_cflags "")
if ( NOT "${CMAKE_BUILD_TYPE}" STREQUAL "Debug" )
  #Aggressively target native platform + a few other optimisations (see also
  #https://github.com/mctools/simplebuild/issues/73). For now we assume the
  #compiler understands all of these:
  #NB: -march=native -mtune=native changes results in some NCrystal unit tests.
  set( sbld_extra_ccxx_cflags "${sbld_extra_ccxx_cflags} -O3 -DNDEBUG -fno-math-errno")# -march=native -mtune=native")
  #Disabling -flto for now, I suspect if causes issues on macos...:
  if ( NOT SBLD_ISINTEL )
    #NB: Not adding -flto=auto for now, since we saw some weird errors of uncaught exceptions on macos.
    set( sbld_extra_ccxx_cflags "${sbld_extra_ccxx_cflags} -ftree-vectorize")
  endif()
endif()
if ( SBLD_ISINTEL )
  #Intel defaults to the equivalent of -ffast-math, revert back to proper math:
  set( sbld_extra_ccxx_cflags "${sbld_extra_ccxx_cflags} -fp-model=precise")
endif()
if ( SBLD_RELDBG_MODE )
  #NB: Fortran -g is handled in ExtDep_Fortran.cmake
  set( sbld_extra_ccxx_cflags "${sbld_extra_ccxx_cflags} -g")
endif()
if ( "${CMAKE_BUILD_TYPE}" STREQUAL "Debug" )
  set( sbld_extra_ccxx_cflags "${sbld_extra_ccxx_cflags} -O0")
endif()

if ( sbld_extra_ccxx_cflags )
  set(SBLD_GLOBAL_COMPILE_FLAGS_CXX "${SBLD_GLOBAL_COMPILE_FLAGS_CXX} ${sbld_extra_ccxx_cflags}")
  set(SBLD_GLOBAL_COMPILE_FLAGS_C     "${SBLD_GLOBAL_COMPILE_FLAGS_C} ${sbld_extra_ccxx_cflags}")
endif()

#To be filled with versions of global ext deps (Python):
set(SBLD_GLOBAL_VERSION_DEPS_CXX "")
set(SBLD_GLOBAL_VERSION_DEPS_C "")
set(SBLD_GLOBAL_VERSION_DEPS_Fortran "")

include("Utils.cmake")
include("Detect.cmake")
include("WriteResults.cmake")
#Avoid unused variable warnings for various things set in CMAKE_ARGS:
fake_usage_cmake_args()
