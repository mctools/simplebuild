#This "external" is here to make sure we always get the correct link flag for dlopen and friends, usually "-ldl".

#We assume DL support is always present, and that an empty CMAKE_DL_LIBS simply
#means that it does not need a special link flag to enable.

set(HAS_DL 1)
set(ExtDep_DL_VERSION "-")
set(ExtDep_DL_COMPILE_FLAGS "")
set(ExtDep_DL_LINK_FLAGS "")

if (CMAKE_DL_LIBS)
  foreach(tmp ${CMAKE_DL_LIBS})
    set(ExtDep_DL_LINK_FLAGS "${ExtDep_DL_LINK_FLAGS} ${CMAKE_LINK_LIBRARY_FLAG}${tmp}")
  endforeach()
endif()
