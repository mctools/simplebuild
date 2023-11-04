EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import ase; import ase.io;print (ase.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_ASE 1)
  string(STRIP "${tmp}" ExtDep_ASE_VERSION)
  set(ExtDep_ASE_COMPILE_FLAGS "")
  set(ExtDep_ASE_LINK_FLAGS "")
else()
  set(HAS_ASE 0)
endif()
