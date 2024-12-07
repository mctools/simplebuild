#This is the builtin tomllib module in python 3.11+ and otherwise it is the
#third party tomli module.

set( HAS_PyToml 0 )

if ( "${PYTHON_VERSION_STRING}" VERSION_GREATER_EQUAL "3.11.0" )
  set( HAS_PyToml 1 )
  set( ExtDep_PyToml_VERSION "${PYTHON_VERSION_STRING}" )
  set( ExtDep_PyToml_COMPILE_FLAGS "" )
  set( ExtDep_PyToml_LINK_FLAGS "" )
else()
  execute_process(
    COMMAND "${Python_EXECUTABLE}" "-c"
    "import tomli;print (tomli.__version__)"
    OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec
    ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  if ("x${tmp_ec}" STREQUAL "x0")
    set( HAS_PyToml 1 )
    string(STRIP "${tmp}" ExtDep_PyToml_VERSION)
    set( ExtDep_PyToml_COMPILE_FLAGS "" )
    set( ExtDep_PyToml_LINK_FLAGS "" )
  endif()
endif()
