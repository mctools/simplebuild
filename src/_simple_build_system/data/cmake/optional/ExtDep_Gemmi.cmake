EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import gemmi; import gemmi.cif;print (gemmi.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Gemmi 1)
  string(STRIP "${tmp}" ExtDep_Gemmi_VERSION)
  set(ExtDep_Gemmi_COMPILE_FLAGS "")
  set(ExtDep_Gemmi_LINK_FLAGS "")
else()
  set(HAS_Gemmi 0)
endif()
