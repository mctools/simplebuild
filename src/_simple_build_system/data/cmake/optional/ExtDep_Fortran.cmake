set(tmp_abort_fortran "0" )
if (APPLE AND UNIX AND NOT Fortran)
  #Dont even bother looking for fortran on OSX unless gfortran is in the path
  #or Fortran=1 is specified. This is because the cmake detection for the
  #missing fortran is veeeeery slow and we will bother most users.
  EXECUTE_PROCESS(COMMAND "which" "gfortran" OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec
                  ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)
  if (NOT "x${tmp_ec}" STREQUAL "x0" OR NOT EXISTS "${tmp}")
    set(tmp_abort_fortran "1" )
  endif()
endif()

if (NOT tmp_abort_fortran)
  include(CheckLanguage)
  check_language(Fortran)
  if (CMAKE_Fortran_COMPILER)
    enable_language(Fortran)
  else()
    set( tmp_abort_fortran "1" )
  endif()
endif()

if ( NOT tmp_abort_fortran )
  set(HAS_Fortran 1)
  if ( SBLD_RELDBG_MODE )
    set(ExtDep_Fortran_COMPILE_FLAGS "-g")
  else()
    set(ExtDep_Fortran_COMPILE_FLAGS "")
  endif()

  set(ExtDep_Fortran_LINK_FLAGS "")
  list(REMOVE_DUPLICATES CMAKE_Fortran_IMPLICIT_LINK_LIBRARIES)
  set(tmp_fortran_striplgcc OFF)
  if (APPLE AND UNIX AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    #In the special case OSX+Clang, we forbid any -lgcc* to creep in via the
    #detected fortran link flags. This is a nasty unmaintainable workaround, but
    #at least works for now (see DGSW-442):
    set(tmp_fortran_striplgcc ON)
  endif()
  foreach(tmp ${CMAKE_Fortran_IMPLICIT_LINK_LIBRARIES})
    if ("${tmp}" STREQUAL gfortranbegin)
        #-lgfortranbegin is ONLY used when linking a fortran executable (it adds main which inits and calls fortran MAIN__)
        set(CMAKE_Fortran_EXECLINK_FLAGS "-lgfortranbegin")
    else()
      if (NOT tmp_fortran_striplgcc OR NOT tmp MATCHES "^gcc.*" )
        set(ExtDep_Fortran_LINK_FLAGS "${ExtDep_Fortran_LINK_FLAGS} -l${tmp}")
      endif()
    endif()
  endforeach()
  #Version (including the name since there are several implementations):
  execute_process(COMMAND ${CMAKE_Fortran_COMPILER} "-dumpversion" OUTPUT_VARIABLE TMP  OUTPUT_STRIP_TRAILING_WHITESPACE)
  string(REPLACE "\n" ";" TMP "${TMP}")
  string(REPLACE " " ";" TMP "${TMP}")
  list(LENGTH TMP tmp2)
  if (${tmp2} GREATER 20)
    list(GET TMP 0 tmp3)
    if ("x${tmp3}" STREQUAL "xGNU")
      list(GET TMP 3 tmp4)
      set(TMP "${tmp4}")
    endif()
  endif()
  set(ExtDep_Fortran_VERSION "${CMAKE_Fortran_COMPILER_ID}/${TMP}")#Must include both name and number
else()
  set(HAS_Fortran 0)
endif()

#NB: On DMSC this seems to pick the intel fortran compiler rather than gfortran.

# If we ever need more advanced fortran support then we could look at:
# http://www.cmake.org/Wiki/CMakeForFortranExample
# And there is also the whole FortranCInterface issue.
