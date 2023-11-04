# Most packages using matplotlib does not need to specify this as an explicit
# dependency, unless it is integral to it's functionality (a prime example would
# be a package whose unit tests depends on numpy being available).

EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import matplotlib;print (matplotlib.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_matplotlib 1)
  string(STRIP "${tmp}" ExtDep_matplotlib_VERSION)
  set(ExtDep_matplotlib_COMPILE_FLAGS "")
  set(ExtDep_matplotlib_LINK_FLAGS "")
else()
  set(HAS_matplotlib 0)
endif()
