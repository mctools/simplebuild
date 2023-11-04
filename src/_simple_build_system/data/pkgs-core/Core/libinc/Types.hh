#ifndef Core_Types_hh
#define Core_Types_hh

//Provides types such as std::uint32_t and defines such as UINT32_MAX, INT16_MAX, etc.
//Also provides PRIu64 etc. for format strings.

#ifndef __STDC_LIMIT_MACROS
#  define __STDC_LIMIT_MACROS
#endif
#ifndef __STDC_CONSTANT_MACROS
#  define __STDC_CONSTANT_MACROS
#endif
#include <cstdint>
#include <climits>
#include <cfloat>//DBL_MAX etc
#ifndef __STDC_FORMAT_MACROS
#  define __STDC_FORMAT_MACROS
#endif
#include <inttypes.h>//cinttypes.h not available on osx

#endif
