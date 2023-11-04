# For now we only detect presence of python module, we do not require (or add
# appropriate flags for) compilation against numpy from C/C++.
#
# Most packages using numpy does not need to specify this as an explicit
# dependency, unless it is integral to it's functionality (a prime example would
# be a package whose unit tests depends on numpy being available).

EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import numpy;print (numpy.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Numpy 1)
  string(STRIP "${tmp}" ExtDep_Numpy_VERSION)
  set(ExtDep_Numpy_COMPILE_FLAGS "")
  set(ExtDep_Numpy_LINK_FLAGS "")
else()
  set(HAS_Numpy 0)
endif()
