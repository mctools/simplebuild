# For now we only detect presence of python module, we do not require (or add
# appropriate flags for) compilation against scipy from C/C++.
#
# Most packages using scipy does not need to specify this as an explicit
# dependency, unless it is integral to it's functionality (a prime example would
# be a package whose unit tests depends on scipy being available).

EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import scipy;print (scipy.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_Scipy 1)
  string(STRIP "${tmp}" ExtDep_Scipy_VERSION)
  set(ExtDep_Scipy_COMPILE_FLAGS "")
  set(ExtDep_Scipy_LINK_FLAGS "")
else()
  set(HAS_Scipy 0)
endif()
