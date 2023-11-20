set(HAS_ZLib 0)
if (NOT SBLD_VERBOSE)
  set(ZLIB_FIND_QUIETLY ON)
endif()
set( tmp_zlib_find_package_args "ZLIB" "1.2.8" )
FIND_PACKAGE(${tmp_zlib_find_package_args})
if (ZLIB_FOUND)
    set(HAS_ZLib 1)
    extract_extdep_flags(
      CXX
      "${tmp_zlib_find_package_args}"
      "ZLIB::ZLIB" ""
      ExtDep_ZLib_COMPILE_FLAGS
      ExtDep_ZLib_LINK_FLAGS
    )
    set(ExtDep_ZLib_LINK_FLAGS "${ZLIB_LIBRARIES}")
    if ( DEFINED "ZLIB_VERSION" )
      #cmake 3.26+
      set(ExtDep_ZLib_VERSION "${ZLIB_VERSION}")
    else()
      #legacy
      set(ExtDep_ZLib_VERSION "${ZLIB_VERSION_STRING}")
    endif()
endif()
