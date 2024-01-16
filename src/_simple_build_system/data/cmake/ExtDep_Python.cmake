#Reconfigure when python version changed
set(autoreconf_bin_Python "python3;python")
set(autoreconf_env_Python "PYTHONPATH;PYTHONHOME;CONDA_PREFIX")

#For consistency, always try to guide the find_package call towards the python3 in the path:
EXECUTE_PROCESS(COMMAND "which" "python3"
                OUTPUT_VARIABLE Python_EXECUTABLE
                RESULT_VARIABLE tmp_ec
                ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE)
if (NOT "x${tmp_ec}" STREQUAL "x0" OR NOT EXISTS "${Python_EXECUTABLE}")
  message(FATAL_ERROR "No python3 interpreter in PATH")
endif()
file(REAL_PATH "${Python_EXECUTABLE}" tmp_python_exec_in_path )

if ( SBLD_VERBOSE )
  find_package( Python 3.8 COMPONENTS Interpreter Development REQUIRED )
else()
  find_package( Python 3.8 COMPONENTS Interpreter Development REQUIRED QUIET )
endif()

message( STATUS "Python executable: ${Python_EXECUTABLE}")
set(PYTHON_VERSION_STRING "${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}.${Python_VERSION_PATCH}")
message( STATUS "Python version: ${PYTHON_VERSION_STRING}")
if ( NOT Python_INTERPRETER_ID STREQUAL "Python" )
  message( FATAL_ERROR "Python implementation does not appear to be CPython.")
endif()
file(REAL_PATH "${Python_EXECUTABLE}" tmp_python_exec_found )
if ( NOT "x${tmp_python_exec_found}" STREQUAL "x${tmp_python_exec_in_path}" )
  message( FATAL_ERROR "CMake found a different Python interpreter (${tmp_python_exec_found}) than the python3 one in the path (${tmp_python_exec_in_path}).")
endif()

list(APPEND SBLD_GLOBAL_VERSION_DEPS_CXX "Python##${PYTHON_VERSION_STRING}")
list(APPEND SBLD_GLOBAL_VERSION_DEPS_C "Python##${PYTHON_VERSION_STRING}")
