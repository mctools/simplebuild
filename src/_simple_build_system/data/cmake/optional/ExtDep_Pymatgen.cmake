EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import pymatgen.symmetry.analyzer; import pymatgen.core;print (pymatgen.core.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Pymatgen 1)
  string(STRIP "${tmp}" ExtDep_Pymatgen_VERSION)
  set(ExtDep_Pymatgen_COMPILE_FLAGS "")
  set(ExtDep_Pymatgen_LINK_FLAGS "")
else()
  set(HAS_Pymatgen 0)
endif()
