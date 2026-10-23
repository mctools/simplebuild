include_guard()

get_filename_component( EXTRACT_DEPINFO_PYSCRIPT "${CMAKE_CURRENT_LIST_DIR}/extract_flags_helper.py" REALPATH )

function( extract_extdep_flags language find_package_arg_list deptargets_list cmake_args_list resvar_cflags resvar_linkflags )
  string(JOIN "@@" tmp ${deptargets_list})
  extract_extdep_flags_multi( "${language}" "${find_package_arg_list}" "${cmake_args_list}" tmpres "${tmp}" )
  set( ${resvar_cflags} "${tmpres_cflags_0}" PARENT_SCOPE )
  set( ${resvar_linkflags} "${tmpres_linkflags_0}" PARENT_SCOPE )
endfunction()

function( _extract_extdep_flags_json_list json resvar )
  #(NB: Do not name the variable "n", since if(n) means if(FALSE)):
  string(JSON nelem LENGTH ${json})
  set( res "" )
  if ( nelem )
    math(EXPR idxmax "${nelem}-1")
    foreach( idx RANGE ${idxmax} )
      string( JSON elem GET "${json}" ${idx} )
      list( APPEND res "${elem}" )
    endforeach()
  endif()
  set( ${resvar} "${res}" PARENT_SCOPE )
endfunction()

# Like extract_extdep_flags, but for several sets of targets at once (in a
# single CMake run, which is much faster than several runs). Each additional
# argument is a set of targets ("@@"-separated if more than one target), and
# the flags for the i'th set (counting from 0) are returned in the variables
# <resvar_prefix>_cflags_<i> and <resvar_prefix>_linkflags_<i>.
function( extract_extdep_flags_multi language find_package_arg_list cmake_args_list resvar_prefix )
  set( cmd "${Python_EXECUTABLE}" "${EXTRACT_DEPINFO_PYSCRIPT}"
    --cmakecommand "${CMAKE_COMMAND}" --respectcmakeargs
    -l "${language}"
    -f -o stdout_json )
  string(JOIN "@@" tmp ${find_package_arg_list})
  list( APPEND cmd --findpackage "${tmp}" )
  foreach( deptargets ${ARGN} )
    list( APPEND cmd --deptargets "${deptargets}" )
  endforeach()
  if ( cmake_args_list )
    list( APPEND cmd -- )
    foreach( tmp ${cmake_args_list} )
      if ( tmp )
        list( APPEND cmd "${tmp}" )
      endif()
    endforeach()
  endif()
  if ( SBLD_VERBOSE )
    string( JOIN " " tmp ${cmd} )
    message( STATUS "About to execute: ${tmp}" )
  endif()
  execute_process( COMMAND ${cmd} OUTPUT_VARIABLE tmp COMMAND_ERROR_IS_FATAL ANY )
  string(JSON extra_list GET "${tmp}" "extra_list")
  string(JSON nsets LENGTH ${extra_list})
  math(EXPR idxmax "${nsets}-1")
  foreach( idx RANGE ${idxmax} )
    string(JSON obj_extra GET "${extra_list}" ${idx})
    string(JSON array_cf GET "${obj_extra}" "compileflags")
    string(JSON array_lf GET "${obj_extra}" "linkflags")
    _extract_extdep_flags_json_list( "${array_cf}" res_cf )
    _extract_extdep_flags_json_list( "${array_lf}" res_lf )
    set( ${resvar_prefix}_cflags_${idx} "${res_cf}" PARENT_SCOPE )
    set( ${resvar_prefix}_linkflags_${idx} "${res_lf}" PARENT_SCOPE )
  endforeach()
endfunction()
