set(HAS_MCPL 0)

set(autoreconf_bin_MCPL "mcpl-config;mcpltool")

function(
    detect_system_mcpl
    resvar_found
    resvar_version
    resvar_cxx_cflags
    resvar_c_cflags
    resvar_linkflags
    )

  set( ${resvar_found} 0 PARENT_SCOPE )

  if ( SBLD_VERBOSE )
    message( STATUS "Checking if can import mcpl module in Python...")
  endif()
  execute_process(
    COMMAND "${Python_EXECUTABLE}" "-c" "import mcpl"
    OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec
    ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if ( NOT "x${tmp_ec}" STREQUAL "x0")
    if ( SBLD_VERBOSE )
      message( STATUS "... Failed to import mcpl module in Python.")
    endif()
    return()
  endif()
  if ( SBLD_VERBOSE )
    message( STATUS "... Successfully imported mcpl module in Python.")
  endif()
  set( cmd mcpl-config --show cmakedir )
  if ( SBLD_VERBOSE )
    string( JOIN " " tmp ${cmd} )
    message( STATUS "Invoking:" ${tmp})
  else()
    list( APPEND cmd ERROR_QUIET )
  endif()
  execute_process( COMMAND ${cmd}
    OUTPUT_VARIABLE MCPL_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE cmd_exitcode
    )
  if ( NOT "x${cmd_exitcode}" STREQUAL "x0" )
    return()
  endif()
  set( findpkgargs MCPL 1.6.2 NO_MODULE NO_DEFAULT_PATH )
  if ( SBLD_VERBOSE )
    message( STATUS "Found MCPL_DIR=${MCPL_DIR}")
    string( JOIN " " tmp ${findpkgargs} )
    message( STATUS "Trying to invoke find_package( ${tmp} )." )
  endif()
  set( preserve_MCPL_DIR "${MCPL_DIR}" )#work around bug in MCPL <= 1.9.80 where the find_package call would override MCPL_DIR.
  find_package( ${findpkgargs} )
  set( MCPL_DIR "${preserve_MCPL_DIR}" )
  if ( NOT MCPL_FOUND )
    if ( SBLD_VERBOSE )
      message( STATUS "The find_package call failed.")
    endif()
    return()
  endif()
  if ( SBLD_VERBOSE )
    message( STATUS "Now trying to detect CXX settings for MCPL.")
  endif()
  extract_extdep_flags(
    CXX "${findpkgargs}" "MCPL::mcpl" "-DMCPL_DIR=${MCPL_DIR}"
    mcpl_cxx_cflags mcpl_cxx_linkflags
    )
  if ( SBLD_VERBOSE )
    message( STATUS "Now trying to detect C settings for MCPL.")
  endif()
  extract_extdep_flags(
    C "${findpkgargs}" "MCPL::mcpl" "-DMCPL_DIR=${MCPL_DIR}"
    mcpl_c_cflags mcpl_c_linkflags
    )
  if ( NOT "x${mcpl_c_linkflags}" STREQUAL "x${mcpl_cxx_linkflags}" )
    message( FATAL_ERROR "Found different MCPL link flags for c++ and c!!")
    return()
  endif()

  #Adding -I${MCPL_INCDIR} directly to the flags for added robustness, since
  #extract_extdep_flags might miss it if it was already in a default include
  #path for the secondary cmake process:
  list( APPEND mcpl_cxx_cflags "-I${MCPL_INCDIR}" )
  list( APPEND mcpl_c_cflags "-I${MCPL_INCDIR}" )

  #Convert from list to single string:
  string( REPLACE ";" " " mcpl_cxx_cflags "${mcpl_cxx_cflags}" )
  string( REPLACE ";" " " mcpl_c_cflags "${mcpl_c_cflags}" )
  string( REPLACE ";" " " mcpl_cxx_linkflags "${mcpl_cxx_linkflags}" )
  string( REPLACE ";" " " mcpl_c_linkflags "${mcpl_c_linkflags}" )

  set( ${resvar_found} 1 PARENT_SCOPE )
  set( ${resvar_version} "${MCPL_VERSION}" PARENT_SCOPE )
  set( ${resvar_cxx_cflags} "${mcpl_cxx_cflags}" PARENT_SCOPE )
  set( ${resvar_c_cflags} "${mcpl_c_cflags}" PARENT_SCOPE )
  set( ${resvar_linkflags} "${mcpl_c_linkflags}" PARENT_SCOPE )
endfunction()

detect_system_mcpl(
  HAS_MCPL
  ExtDep_MCPL_VERSION
  ExtDep_MCPL_COMPILE_FLAGS_CXX
  ExtDep_MCPL_COMPILE_FLAGS_C
  ExtDep_MCPL_LINK_FLAGS
)
#FIXME: ONLY ENABLE IF CAN ALSO IMPORT PYTHON MODULE???
