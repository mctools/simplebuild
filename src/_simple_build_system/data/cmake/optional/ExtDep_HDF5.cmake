set(HAS_HDF5 0)
if (NOT SBLD_VERBOSE)
  set(HDF5_FIND_QUIETLY ON)
endif()
FIND_PACKAGE(HDF5 COMPONENTS CXX)
if (HDF5_FOUND)
    set(TMP_HDF5_HDR_FOUND 0)
    set(TMP_INCDIRFLAGS "")
    set(TMP_INCDIRS "")
    foreach(TMP_INCDIR ${HDF5_INCLUDE_DIRS})
      if (EXISTS ${TMP_INCDIR}/H5Cpp.h)
        set(TMP_HDF5_HDR_FOUND 1)
      endif()
      set(TMP_INCDIRFLAGS "${TMP_INCDIRFLAGS} -I${TMP_INCDIR} -isystem${TMP_INCDIR}")
      set(TMP_INCDIRS "${TMP_INCDIRFLAGS} ${TMP_INCDIRS}")
    endforeach()
    if (NOT TMP_HDF5_HDR_FOUND)
        message( STATUS "HDF5 found at ${TMP_INCDIRS} but without C++ header H5Cpp.h")
    else()
        set(HAS_HDF5 1)
        if (NOT "x${HDF5_INCLUDE_DIRS}" STREQUAL "x/usr/include")
          set(ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS} ${TMP_INCDIRFLAGS}")
        else()
          set(ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS}")
        endif()
        foreach(cflag ${HDF5_DEFINITIONS})
          set(ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS} ${cflag}")
        endforeach()
        if (CMAKE_BUILD_TYPE STREQUAL "DEBUG")
          #Setting _FORTIFY_SOURCE results in a warning when not compiling with optimisations enabled
          string(REPLACE "-D_FORTIFY_SOURCE=2" "" ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS}")
        endif()
        #The _BSD_SOURCE and _SVID_SOURCE feature test macros are deprecated as
        #of glibc 2.19.90 (2.20 devel). We assume this means gcc>=4.9:
        if ("x${CMAKE_CXX_COMPILER_ID}" STREQUAL "xGNU")
          if (NOT CMAKE_CXX_COMPILER_VERSION VERSION_LESS 4.9)
            string(REPLACE "-D_BSD_SOURCE" "-D_DEFAULT_SOURCE" ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS}")
            string(REPLACE "-D_BSD_SOURCE" "-D_DEFAULT_SOURCE" ExtDep_HDF5_COMPILE_FLAGS "${ExtDep_HDF5_COMPILE_FLAGS}")
          endif()
        endif()
        findpackage_liblist_to_flags("${HDF5_LIBRARIES}" "" ExtDep_HDF5_LINK_FLAGS)
        if (NOT HDF5_VERSION_STRING)
          if (HDF5_DIFF_EXECUTABLE)
            execute_process(COMMAND "${HDF5_DIFF_EXECUTABLE}" "-V" OUTPUT_VARIABLE TMP OUTPUT_STRIP_TRAILING_WHITESPACE)
            separate_arguments(TMP)
            list(GET TMP -1 TMP)
            set(ExtDep_HDF5_VERSION "${TMP}")
          else()
            set(ExtDep_HDF5_VERSION "unknown")
          endif()
        else()
          set(ExtDep_HDF5_VERSION "${HDF5_VERSION_STRING}")
        endif()
    endif()
endif()