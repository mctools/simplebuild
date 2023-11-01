EXECUTE_PROCESS(COMMAND "mantidpython" "--version"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Mantidpython 1)
  string(STRIP "${tmp}" ExtDep_Mantidpython_VERSION)
  set(ExtDep_Mantidpython_COMPILE_FLAGS "")
  set(ExtDep_Mantidpython_LINK_FLAGS "")
else()
  set(HAS_Mantidpython 0)
endif()
