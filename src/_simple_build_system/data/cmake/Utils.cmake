
function(declare_includes_as_system_headers cflags_varname)
  #Go through compilation flags and looks for include paths (-Ixxx):
  if ("x${${cflags_varname}}" STREQUAL x)
    return()
  endif()
  set(sysdirs "")
  string(REPLACE " " ";" tmp ${${cflags_varname}})
  list(REMOVE_ITEM tmp "-I/usr/include")#important to remove to avoid conflicts with other extdeps
  list(REMOVE_ITEM tmp "-isystem/usr/include")
  set(out "")
  foreach(cflag ${tmp})
    set(out "${out} ${cflag}")
    string(REGEX MATCH "^-I.*$" tmp2 "${cflag}")
    if (tmp2)
      string(REPLACE "-I" "" tmp3 "${tmp2}")
      get_filename_component(tmp4 "${tmp3}" ABSOLUTE)
      if (EXISTS "${tmp4}/")
        list(APPEND sysdirs "${tmp4}")
      endif()
    endif()
  endforeach()
  #Prune a bit
  list(REMOVE_DUPLICATES sysdirs)
  #Add -isystem flags:
  foreach(tmp ${sysdirs})
    set(out "${out} -isystem${tmp}")
  endforeach()
  set(${cflags_varname} "${out}" PARENT_SCOPE)
endfunction()

function(fixvar input resvar)
  set(out "")
  set(SKIPNEXT 0)
  foreach(var ${input})
    if (NOT SKIPNEXT)
      if ("${var}" STREQUAL "optimized")
        if (DEBUG)
          set(SKIPNEXT 1)
        else()
          set(SKIPNEXT 0)
        endif()
      elseif("${var}" STREQUAL "debug")
        if (DEBUG)
          set(SKIPNEXT 0)
        else()
          set(SKIPNEXT 1)
        endif()
      elseif(NOT SKIPNEXT)
        list(APPEND out "${var}")
        set(SKIPNEXT 0)
      else()
        set(SKIPNEXT 0)
      endif()
    else()
      set(SKIPNEXT 0)
    endif()
  endforeach()
  set(${resvar} "${out}" PARENT_SCOPE)
endfunction()

function(findpackage_liblist_to_flags libs libdirs resvar)
  fixvar("${libs}" libs)
  fixvar("${libdirs}" libdirs)
  set(out "")
  foreach(libdir ${libdirs})
    set(out "${out} -L${libdir}")
  endforeach()
  foreach(lib ${libs})
    set(out "${out} ${lib}")
  endforeach()
  set("${resvar}" "${out}" PARENT_SCOPE)
endfunction()

function( decode_link_options link_options language resvar )
  #Decodes the LINKER: syntax
  #(cf. https://cmake.org/cmake/help/latest/command/add_link_options.html)

  if( "${CMAKE_VERSION}" VERSION_LESS "3.13.0")
    #LINKER: syntax not introduced yet:
    set( ${resvar} "${link_options}" PARENT_SCOPE )
  endif()

  if ( link_options MATCHES "SHELL:" )
    message(FATAL_ERROR "\"SHELL:\" syntax encountered in link options. This is currently not supported.")
  endif()

  if ( NOT link_options MATCHES "LINKER:" )
    set( ${resvar} "${link_options}" PARENT_SCOPE )
    return()
  endif()
  string(REPLACE " " ";" link_opts_list "${link_options}")
  list(JOIN CMAKE_${language}_LINKER_WRAPPER_FLAG " " wrapflag )
  if ( wrapflag MATCHES "  $")
    string(REGEX REPLACE "  $" " " wrapflag "${wrapflag}")
  endif()
  #set( wrapflag "${CMAKE_${language}_LINKER_WRAPPER_FLAG}" )
  if ( DEFINED CMAKE_${language}_LINKER_WRAPPER_FLAG_SEP )
    set( has_wrapflagsep ON )
    set( wrapflagsep "${CMAKE_${language}_LINKER_WRAPPER_FLAG_SEP}" )
  else()
    set( has_wrapflagsep OFF )
  endif()

  set(tmp "")
  foreach( elem ${link_opts_list} )
    if (  elem MATCHES "^LINKER:" )
      string(SUBSTRING "${elem}" 7 -1 elem )
      if ( NOT elem MATCHES "," )
        list(APPEND tmp "${wrapflag}${elem}")
      else()
        if ( has_wrapflagsep )
          string(REPLACE "," "${wrapflagsep}" elem "${elem}")
          list(APPEND tmp "${wrapflag}${elem}")
        else()
          string(REPLACE "," " ${wrapflag}" elem "${elem}")
          list(APPEND tmp "${wrapflag}${elem}")
        endif()
      endif()
    else()
      list(APPEND tmp "${elem}")
    endif()
  endforeach()
  list(JOIN tmp " " tmp)
  set( ${resvar} "${tmp}" PARENT_SCOPE )
endfunction()

function( fake_usage_cmake_args )
  string( REPLACE " " ";" tmp_cmake_args_list "$ENV{CMAKE_ARGS}" )
  foreach( tmp ${tmp_cmake_args_list} )
    if ( NOT "${tmp}" MATCHES "^-D..*=..*$" )
      continue()
    endif()
    string( REPLACE "=" ";" parts "${tmp}" )
    list( POP_FRONT parts tmp )
    string( SUBSTRING "${tmp}" 2 -1 tmp )
    #Fake usage:
    if ( DEFINED "${tmp}" )
      set( "${tmp}" "${${tmp}}" )
    endif()
  endforeach()
endfunction()

function( strip_cpp_version_flags varname )
  set( tmp "${${varname}}" )
  set( blocklist
    "-std=c++98"
    "-std=c++0x" "-std=c++11" "-std=gnu++11"
    "-std=c++1y" "-std=c++14" "-std=gnu++14"
    "-std=c++1z" "-std=c++17" "-std=gnu++17"
    "-std=c++2a" "-std=c++20" "-std=gnu++20"
    "-std=c++2b" "-std=c++23" "-std=gnu++23"
    )
  if( tmp MATCHES ";" )
    #we are dealing with a list
    set( res "" )
    foreach( entry ${tmp} )
      if ( NOT "${entry}" IN_LIST blocklist )
        list( APPEND res "${entry}" )
      endif()
    endforeach()
    set( "${varname}" "${res}" PARENT_SCOPE )
  else()
    foreach( entry ${blocklist} )
      string(REPLACE "${entry}" "" tmp "${tmp}")
    endforeach()
    set( "${varname}" "${tmp}" PARENT_SCOPE )
  endif()
endfunction()
