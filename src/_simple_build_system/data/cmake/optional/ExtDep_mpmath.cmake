EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import mpmath; print (mpmath.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_mpmath 1)
  string(STRIP "${tmp}" ExtDep_mpmath_VERSION)
  set(ExtDep_mpmath_COMPILE_FLAGS "")
  set(ExtDep_mpmath_LINK_FLAGS "")
else()
  set(HAS_mpmath 0)
endif()
