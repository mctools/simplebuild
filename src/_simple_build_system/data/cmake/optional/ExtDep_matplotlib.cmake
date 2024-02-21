# Most packages using matplotlib does not need to specify this as an explicit
# dependency, unless it is integral to it's functionality (a prime example of a
# package needing it would be a package whose unit tests depends on matplotlib
# being available).

#NB: "import matplotlib.pyplot" (and not just "import matplotlib") is a good
#test, but has an additional advantage in that it ensures the matplotlib font
#cache building is triggered, so we don't get output in the middle of our unit
#tests later..

EXECUTE_PROCESS(COMMAND "${Python_EXECUTABLE}" "-c" "import matplotlib;import matplotlib.pyplot;print (matplotlib.__version__)"
                OUTPUT_VARIABLE tmp RESULT_VARIABLE tmp_ec ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)

if ("x${tmp_ec}" STREQUAL "x0")
  set(HAS_matplotlib 1)
  string(STRIP "${tmp}" ExtDep_matplotlib_VERSION)
  set(ExtDep_matplotlib_COMPILE_FLAGS "")
  set(ExtDep_matplotlib_LINK_FLAGS "")
else()
  set(HAS_matplotlib 0)
endif()
