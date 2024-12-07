#Just before writing, we also decodes all the link flags (here for global
#variables and further below for each extdep):
decode_link_options( "${SBLD_GLOBAL_LINK_FLAGS}" CXX SBLD_GLOBAL_LINK_FLAGS )
decode_link_options( "${SBLD_GLOBAL_LINK_FLAGS_PREPENDED}" CXX SBLD_GLOBAL_LINK_FLAGS_PREPENDED )
foreach( lang C CXX Fortran )
  decode_link_options( "${CMAKE_${lang}_EXECLINK_FLAGS}" ${lang} CMAKE_${lang}_EXECLINK_FLAGS )
  decode_link_options( "${CMAKE_${lang}_LINK_FLAGS}" ${lang} CMAKE_${lang}_EXECLINK_FLAGS )
endforeach()

set(output_file ${CMAKE_CURRENT_BINARY_DIR}/${output_filename})
file(WRITE ${output_file} "#Dependency information extracted via cmake\n")
set(oa APPEND ${output_file})

file(${oa} "VAR@${}CMAKE_BUILD_TYPE@${CMAKE_BUILD_TYPE}\n")
foreach( tmp
    "PYBIND11_EMBED_CFLAGS_LIST"
    "PYBIND11_EMBED_LINKFLAGS_LIST"
    "PYBIND11_MODULE_CFLAGS_LIST"
    "PYBIND11_MODULE_LINKFLAGS_LIST"
    "PYBIND11_VERSION"
    )
  file(${oa} "VAR@${}${tmp}@${${tmp}}\n")
endforeach()

file(${oa} "VAR@${}CMAKE_VERSION@${CMAKE_VERSION}\n")
file(${oa} "VAR@${}CMAKE_SYSTEM@${CMAKE_SYSTEM}\n")

#compiler versions (so we can trigger rebuilds on system upgrades):
set(tmplangs "CXX;C")
if (HAS_Fortran)
  list(APPEND tmplangs "Fortran")
endif()

#Sometimes we appear to really need the uppercase version:
string(TOUPPER "${CMAKE_BUILD_TYPE}" SBL_UPPERCASE_CMAKE_BUILD_TYPE)
foreach( lang ${tmplangs} )
  #Annoyingly the casing in CMAKE_BUILD_TYPE (e.g. "Release") is not identical
  #to the casing in the variable names like CMAKE_CXX_FLAGS_RELEASE. Not sure if
  #there is a better way, but at least here is a workaround:
  if ( DEFINED "CMAKE_${lang}_FLAGS_${SBL_UPPERCASE_CMAKE_BUILD_TYPE}" )
    set( "sbl_${lang}_flags_for_buildtype" "${CMAKE_${lang}_FLAGS_${SBL_UPPERCASE_CMAKE_BUILD_TYPE}}")
  elseif ( DEFINED "CMAKE_${lang}_FLAGS_${CMAKE_BUILD_TYPE}" )
    set( "sbl_${lang}_flags_for_buildtype" "${CMAKE_${lang}_FLAGS_${CMAKE_BUILD_TYPE}}")
  endif()
endforeach()

foreach(lang ${tmplangs})
  if(CMAKE_${lang}_COMPILER_VERSION)
    string(REGEX MATCH "([0-9]*)\\.([0-9]*)\\.([0-9]*)" dummy ${CMAKE_${lang}_COMPILER_VERSION})
    set(TMPS "${CMAKE_MATCH_1}.${CMAKE_MATCH_2}.${CMAKE_MATCH_3}")
  else()
    #fallback, hoping compiler supports a meaningful -dumpversion (nb: clang supports this but gives wrong info for compatibility reasons)
    execute_process(COMMAND ${CMAKE_${lang}_COMPILER} "-dumpversion" OUTPUT_VARIABLE TMPS  OUTPUT_STRIP_TRAILING_WHITESPACE)
    string(REPLACE "\n" ";" TMPS "${TMPS}")
  endif()
  execute_process(COMMAND ${CMAKE_${lang}_COMPILER} "--version" OUTPUT_VARIABLE TMPL  OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(REPLACE "\n" ";" TMPL "${TMPL}")
  file(${oa} "VAR@${}CMAKE_${lang}_COMPILER_VERSION_SHORT@${CMAKE_${lang}_COMPILER_ID}/${TMPS}\n")
  file(${oa} "VAR@${}CMAKE_${lang}_COMPILER_VERSION_LONG@${TMPL}\n")
  file(${oa} "VAR@${}SBLD_GLOBAL_VERSION_DEPS_${lang}@${SBLD_GLOBAL_VERSION_DEPS_${lang}}\n")


  file(${oa} "VAR@${}CMAKE_${lang}_OUTPUT_EXTENSION@${CMAKE_${lang}_OUTPUT_EXTENSION}\n")
  file(${oa} "VAR@${}CMAKE_${lang}_COMPILER@${CMAKE_${lang}_COMPILER}\n")
  file(${oa} "VAR@${}CMAKE_${lang}_FLAGS@${CMAKE_${lang}_FLAGS} ${sbl_${lang}_flags_for_buildtype}\n")

  #libstdc++ drags in libm, but in C it might be missing:
  set( tmp_linkflags ${CMAKE_${lang}_LINK_FLAGS} )
  if ( "${lang}" STREQUAL "C" )
    set(tmp_linkflags "${tmp_linkflags} -lm")
  endif()
  file(${oa} "VAR@${}CMAKE_${lang}_LINK_FLAGS@${tmp_linkflags}\n")
endforeach()

file(${oa} "VAR@${}CMAKE_SHARED_LIBRARY_PREFIX@${CMAKE_SHARED_LIBRARY_PREFIX}\n")
file(${oa} "VAR@${}CMAKE_SHARED_LIBRARY_SUFFIX@${CMAKE_SHARED_LIBRARY_SUFFIX}\n")

file(${oa} "VAR@${}SBLD_GLOBAL_COMPILE_FLAGS_C@${SBLD_GLOBAL_COMPILE_FLAGS_C}\n")
file(${oa} "VAR@${}SBLD_GLOBAL_COMPILE_FLAGS_CXX@${SBLD_GLOBAL_COMPILE_FLAGS_CXX}\n")
file(${oa} "VAR@${}SBLD_GLOBAL_LINK_FLAGS@${SBLD_GLOBAL_LINK_FLAGS}\n")
file(${oa} "VAR@${}SBLD_GLOBAL_LINK_FLAGS_PREPENDED@${SBLD_GLOBAL_LINK_FLAGS_PREPENDED}\n")

file(${oa} "VAR@${}SBLD_EXTRA_LDLIBPATHS@${SBLD_EXTRA_LDLIBPATHS}\n")
file(${oa} "VAR@${}SBLD_EXTRA_PATHS@${SBLD_EXTRA_PATHS}\n")
file(${oa} "VAR@${}SBLD_LIBS_TO_SYMLINK@${SBLD_LIBS_TO_SYMLINK}\n")

#quick and dirty, not very portable, just enough (hopefully?) for osx/linux/clang/gcc:
if ( DEFINED CMAKE_SHARED_LIBRARY_RPATH_LINK_C_FLAG
    AND CMAKE_SHARED_LIBRARY_RPATH_LINK_C_FLAG MATCHES ".*rpath-link.*" )
  set( compiler_supports_rpathlink 1 )
else()
  set( compiler_supports_rpathlink 0 )
endif()
file(${oa} "VAR@${}CAN_USE_RPATHLINK_FLAG@${compiler_supports_rpathlink}\n")

foreach(lang ${tmplangs})
  file(${oa} "VAR@${}RULE_${lang}_SHLIB@${CMAKE_${lang}_COMPILER} ${CMAKE_SHARED_LIBRARY_${lang}_FLAGS} [FLAGS] ${CMAKE_SHARED_LIBRARY_CREATE_${lang}_FLAGS} [INPUT] -o [OUTPUT]\n")
  file(${oa} "VAR@${}RULE_${lang}_COMPOBJ@${CMAKE_${lang}_COMPILER} [FLAGS] -c [INPUT] -o [OUTPUT]\n")
  file(${oa} "VAR@${}RULE_${lang}_EXECUTABLE@${CMAKE_${lang}_COMPILER} [FLAGS] ${CMAKE_${lang}_EXECLINK_FLAGS} ${CMAKE_${lang}_LINK_FLAGS} [INPUT] -o [OUTPUT]\n")
  file(${oa} "VAR@${}RPATH_FLAG_${lang}_EXECUTABLE@${CMAKE_EXECUTABLE_RUNTIME_${lang}_FLAG}\n")
  file(${oa} "VAR@${}RPATH_FLAG_${lang}_SHLIB@${CMAKE_SHARED_LIBRARY_RUNTIME_${lang}_FLAG}\n")
endforeach()

foreach(extdep ${extdep_all})
  if (HAS_${extdep})
    decode_link_options( "${ExtDep_${extdep}_LINK_FLAGS}" CXX ExtDep_${extdep}_LINK_FLAGS )
    list(APPEND extdep_present ${extdep})
    file(${oa} "EXT@${extdep}@PRESENT@1\n")
    file(${oa} "EXT@${extdep}@LINK@${ExtDep_${extdep}_LINK_FLAGS}\n")
    file(${oa} "EXT@${extdep}@COMPILE_CXX@${ExtDep_${extdep}_COMPILE_FLAGS_CXX}\n")
    file(${oa} "EXT@${extdep}@COMPILE_C@${ExtDep_${extdep}_COMPILE_FLAGS_C}\n")
    file(${oa} "EXT@${extdep}@VERSION@${ExtDep_${extdep}_VERSION}\n")
    if ( NOT DEFINED "ExtDep_${extdep}_IncludeMapFile" )
      set( "ExtDep_${extdep}_IncludeMapFile" "" )
    endif()
    file(${oa} "EXT@${extdep}@INCLUDEMAPFILE@${ExtDep_${extdep}_INCLUDEMAPFILE}\n")
    if ( NOT DEFINED "ExtDep_${extdep}_FLAGPRIORITY" )
      set( "ExtDep_${extdep}_FLAGPRIORITY" "1000" )
    endif()
    file(${oa} "EXT@${extdep}@FLAGPRIORITY@${ExtDep_${extdep}_FLAGPRIORITY}\n")
  else()
    file(${oa} "EXT@${extdep}@PRESENT@0\n")
  endif()
endforeach()

file(${oa} "VAR@${}autoreconf_bin_list@${extdep_autoreconf_bin_list}\n")
file(${oa} "VAR@${}autoreconf_env_list@${extdep_autoreconf_env_list}\n")


