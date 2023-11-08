set(HAS_NCrystal 0)

set(autoreconf_bin_NCrystal "ncrystal-config;nctool")
set(autoreconf_env_NCrystal "NCRYSTALDIR")

function(
    detect_system_ncrystal
    resvar_found
    resvar_version
    resvar_cxx_cflags
    resvar_c_cflags
    resvar_linkflags
    )

  set( ${resvar_found} 0 PARENT_SCOPE )
  set( cmd ncrystal-config --show cmakedir )
  if ( SBLD_VERBOSE )
    string( JOIN " " tmp ${cmd} )
    message( STATUS "Invoking:" ${tmp})
  else()
    list( APPEND cmd ERROR_QUIET )
  endif()
  execute_process( COMMAND ${cmd}
    OUTPUT_VARIABLE NCrystal_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE cmd_exitcode
    )
  if ( NOT "x${cmd_exitcode}" STREQUAL "x0" )
    return()
  endif()
  set( findpkgargs NCrystal 3.7.1 NO_MODULE NO_DEFAULT_PATH )#TODO: If found but version is too old, and in conda, provide conda command for updating ncrystal version.
  if ( SBLD_VERBOSE )
    message( STATUS "Found NCrystal_DIR=${NCrystal_DIR}")
    string( JOIN " " tmp ${findpkgargs} )
    message( STATUS "Trying to invoke find_package( ${tmp} )." )
  endif()
  set( preserve_NCrystal_DIR "${NCrystal_DIR}" )#work around bug in NCrystal <= 3.7.1 where the find_package call would override NCrystal_DIR.
  find_package( ${findpkgargs} )
  set( NCrystal_DIR "${preserve_NCrystal_DIR}" )
  if ( NOT NCrystal_FOUND )
    if ( SBLD_VERBOSE )
      message( STATUS "The find_package call failed.")
    endif()
    return()
  endif()
  if ( SBLD_VERBOSE )
    message( STATUS "Now trying to detect CXX settings for NCrystal.")
  endif()
  extract_extdep_flags(
    CXX "${findpkgargs}" "NCrystal::NCrystal" "-DNCrystal_DIR=${NCrystal_DIR}"
    ncrystal_cxx_cflags ncrystal_cxx_linkflags
    )
  if ( SBLD_VERBOSE )
    message( STATUS "Now trying to detect C settings for NCrystal.")
  endif()
  extract_extdep_flags(
    C "${findpkgargs}" "NCrystal::NCrystal" "-DNCrystal_DIR=${NCrystal_DIR}"
    ncrystal_c_cflags ncrystal_c_linkflags
    )
  if ( NOT "x${ncrystal_c_linkflags}" STREQUAL "x${ncrystal_cxx_linkflags}" )
    message( FATAL_ERROR "Found different NCrystal link flags for c++ and c!!")
    return()
  endif()

  #Adding -I${NCrystal_INCDIR} directly to the flags for added robustness, since
  #extract_extdep_flags might miss it if it was already in a default include
  #path for the secondary cmake process:
  list( APPEND ncrystal_cxx_cflags "-I${NCrystal_INCDIR}" )
  list( APPEND ncrystal_c_cflags "-I${NCrystal_INCDIR}" )

  #Convert from list to single string:
  string( REPLACE ";" " " ncrystal_cxx_cflags "${ncrystal_cxx_cflags}" )
  string( REPLACE ";" " " ncrystal_c_cflags "${ncrystal_c_cflags}" )
  string( REPLACE ";" " " ncrystal_cxx_linkflags "${ncrystal_cxx_linkflags}" )
  string( REPLACE ";" " " ncrystal_c_linkflags "${ncrystal_c_linkflags}" )

  set( ${resvar_found} 1 PARENT_SCOPE )
  set( ${resvar_version} "${NCrystal_VERSION}" PARENT_SCOPE )
  set( ${resvar_cxx_cflags} "${ncrystal_cxx_cflags}" PARENT_SCOPE )
  set( ${resvar_c_cflags} "${ncrystal_c_cflags}" PARENT_SCOPE )
  set( ${resvar_linkflags} "${ncrystal_c_linkflags}" PARENT_SCOPE )
endfunction()

detect_system_ncrystal( HAS_NCrystal
  ExtDep_NCrystal_VERSION
  ExtDep_NCrystal_COMPILE_FLAGS_CXX
  ExtDep_NCrystal_COMPILE_FLAGS_C
  ExtDep_NCrystal_LINK_FLAGS )
