EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import spglib;print (spglib.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Spglib 1)
  string(STRIP "${tmp}" ExtDep_Spglib_VERSION)
  set(ExtDep_Spglib_COMPILE_FLAGS "")
  set(ExtDep_Spglib_LINK_FLAGS "")
else()
  set(HAS_Spglib 0)
endif()
