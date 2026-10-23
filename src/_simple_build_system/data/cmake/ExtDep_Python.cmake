#Reconfigure when python version changed
set(autoreconf_bin_Python "python3;python")
set(autoreconf_env_Python "PYTHONPATH;PYTHONHOME;CONDA_PREFIX")

#Use the same Python interpreter as simplebuild itself:
if ( NOT SBLD_PYTHON_EXECUTABLE OR NOT EXISTS "${SBLD_PYTHON_EXECUTABLE}" )
  message(FATAL_ERROR "Python interpreter of simplebuild not specified or not found")
endif()
set( Python_EXECUTABLE "${SBLD_PYTHON_EXECUTABLE}" )
file(REAL_PATH "${Python_EXECUTABLE}" tmp_python_exec_requested )

if ( SBLD_VERBOSE )
  find_package( Python 3.9 COMPONENTS Interpreter Development REQUIRED )
else()
  find_package( Python 3.9 COMPONENTS Interpreter Development REQUIRED QUIET )
endif()

message( STATUS "Python executable: ${Python_EXECUTABLE}")
set(PYTHON_VERSION_STRING "${Python_VERSION_MAJOR}.${Python_VERSION_MINOR}.${Python_VERSION_PATCH}")
message( STATUS "Python version: ${PYTHON_VERSION_STRING}")
if ( NOT Python_INTERPRETER_ID STREQUAL "Python" )
  message( FATAL_ERROR "Python implementation does not appear to be CPython.")
endif()
file(REAL_PATH "${Python_EXECUTABLE}" tmp_python_exec_found )
if ( NOT "x${tmp_python_exec_found}" STREQUAL "x${tmp_python_exec_requested}" )
  message( FATAL_ERROR "CMake found a different Python interpreter (${tmp_python_exec_found}) than the one used by simplebuild (${tmp_python_exec_requested}).")
endif()

#The python3 command in the PATH must belong to the same Python installation
#or environment, since scripts starting with "#!/usr/bin/env python3" must be
#able to use the code built here:
find_program( tmp_python3_in_path NAMES python3 NO_CACHE NO_CMAKE_PATH
              NO_CMAKE_ENVIRONMENT_PATH NO_CMAKE_SYSTEM_PATH )
if ( NOT tmp_python3_in_path )
  message( FATAL_ERROR "No python3 command in the PATH (it must be the Python"
    " interpreter used by simplebuild: ${Python_EXECUTABLE})." )
endif()
set( tmp_prefix_code "import sys; print(sys.prefix)" )
execute_process( COMMAND "${Python_EXECUTABLE}" "-c" "${tmp_prefix_code}"
                 OUTPUT_VARIABLE tmp_prefix_sb RESULT_VARIABLE tmp_ec1
                 ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE )
execute_process( COMMAND "${tmp_python3_in_path}" "-c" "${tmp_prefix_code}"
                 OUTPUT_VARIABLE tmp_prefix_path RESULT_VARIABLE tmp_ec2
                 ERROR_QUIET OUTPUT_STRIP_TRAILING_WHITESPACE )
if ( "x${tmp_ec1}" STREQUAL "x0" AND "x${tmp_ec2}" STREQUAL "x0" )
  file(REAL_PATH "${tmp_prefix_sb}" tmp_prefix_sb )
  file(REAL_PATH "${tmp_prefix_path}" tmp_prefix_path )
endif()
if ( NOT "x${tmp_ec1}" STREQUAL "x0" OR NOT "x${tmp_ec2}" STREQUAL "x0"
     OR NOT "x${tmp_prefix_sb}" STREQUAL "x${tmp_prefix_path}" )
  message( FATAL_ERROR "The python3 command in the PATH (${tmp_python3_in_path})"
    " is not from the same Python installation or environment as the Python"
    " interpreter used by simplebuild (${Python_EXECUTABLE}).")
endif()

list(APPEND SBLD_GLOBAL_VERSION_DEPS_CXX "Python##${PYTHON_VERSION_STRING}")
list(APPEND SBLD_GLOBAL_VERSION_DEPS_C "Python##${PYTHON_VERSION_STRING}")
