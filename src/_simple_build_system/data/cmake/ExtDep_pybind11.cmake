function( detect_system_pybind11
    resvar_embed_cflags_list
    resvar_embed_linkflags_list
    resvar_module_cflags_list
    resvar_module_linkflags_list
    resvar_version
    )
  set( cmd "${Python_EXECUTABLE}" -mpybind11 --cmakedir )
  if ( SBLD_VERBOSE )
    string( JOIN " " tmp ${cmd} )
    message( STATUS "Invoking:" ${tmp})
  else()
    list( APPEND cmd ERROR_QUIET )
  endif()
  execute_process( COMMAND ${cmd}
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE cmd_exitcode
    )
  if ( NOT "x${cmd_exitcode}" STREQUAL "x0" )
    message( FATAL_ERROR "Could not find pybind11." )
  endif()
  if ( SBLD_VERBOSE )
    message( STATUS "Found pybind11_DIR=${pybind11_DIR}")
  endif()

  set( cmd "${Python_EXECUTABLE}" -mpybind11 --version )
  if ( SBLD_VERBOSE )
    string( JOIN " " tmp ${cmd} )
    message( STATUS "Invoking:" ${tmp})
  else()
    list( APPEND cmd ERROR_QUIET )
  endif()
  execute_process( COMMAND ${cmd}
    OUTPUT_VARIABLE pybind11_version
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE cmd_exitcode
    )
  if ( NOT "x${cmd_exitcode}" STREQUAL "x0" )
    message( FATAL_ERROR "Could not get version of pybind11." )
  endif()
  set( findpkg_args "pybind11;2.10.4;NO_MODULE;NO_DEFAULT_PATH" )
  set( cmake_args "" )
  list( APPEND cmake_args "-DPython_EXECUTABLE=${Python_EXECUTABLE}" )
  list( APPEND cmake_args "-Dpybind11_DIR=${pybind11_DIR}" )

  extract_extdep_flags( CXX "${findpkg_args}" "pybind11::module" "${cmake_args}" module_cflags module_linkflags )
  extract_extdep_flags( CXX "${findpkg_args}" "pybind11::embed" "${cmake_args}" embed_cflags embed_linkflags )

  #Make sure pybind11 does not overrule the c++ standard:
  strip_cpp_version_flags( module_cflags )
  strip_cpp_version_flags( embed_cflags )

  #Temporary workaround (see https://github.com/pybind/pybind11/issues/5224):
  include(CheckCXXCompilerFlag)
  check_cxx_compiler_flag(
    "-Wno-array-bounds"
    "compiler_supports_Wno-array-bounds"
  )
  check_cxx_compiler_flag(
    "-Wno-stringop-overread"
    "compiler_supports_Wno-stringop-overread"
  )
  if ( compiler_supports_Wno-array-bounds )
    list(APPEND embed_cflags "-Wno-array-bounds")
    list(APPEND module_cflags "-Wno-array-bounds")
  endif()
  if ( compiler_supports_Wno-stringop-overread )
    list(APPEND embed_cflags "-Wno-stringop-overread")
    list(APPEND module_cflags "-Wno-stringop-overread")
  endif()

  #For some reason the -DUSING_pybind11 define does not get added with the
  #above. Try to add it manually and hope it works:
  set( ${resvar_version} "${pybind11_version}" PARENT_SCOPE )
  set( ${resvar_embed_cflags_list} "${embed_cflags} -DUSING_pybind11" PARENT_SCOPE )
  set( ${resvar_embed_linkflags_list} "${embed_linkflags}" PARENT_SCOPE )
  set( ${resvar_module_cflags_list} "${module_cflags} -DUSING_pybind11" PARENT_SCOPE )
  set( ${resvar_module_linkflags_list} "${module_linkflags}" PARENT_SCOPE )
endfunction()

detect_system_pybind11(
  PYBIND11_EMBED_CFLAGS_LIST
  PYBIND11_EMBED_LINKFLAGS_LIST
  PYBIND11_MODULE_CFLAGS_LIST
  PYBIND11_MODULE_LINKFLAGS_LIST
  PYBIND11_VERSION
  )

message( STATUS "Found pybind11 version ${PYBIND11_VERSION}")

if ( SBLD_VERBOSE )
  message( STATUS "pybind11 compilation flags (embed): ${PYBIND11_EMBED_CFLAGS_LIST} " )
  message( STATUS "pybind11 link flags (embed): ${PYBIND11_EMBED_LINKFLAGS_LIST} " )
  message( STATUS "pybind11 compilation flags (module): ${PYBIND11_MODULE_CFLAGS_LIST} " )
  message( STATUS "pybind11 link flags (module): ${PYBIND11_MODULE_LINKFLAGS_LIST} " )
endif()

list(APPEND SBLD_GLOBAL_VERSION_DEPS_CXX "pybind11##${PYBIND11_VERSION}")
list(APPEND SBLD_GLOBAL_VERSION_DEPS_C "pybind11##${PYBIND11_VERSION}")
