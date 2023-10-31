#ifndef Core_FPE_hh
#define Core_FPE_hh

#include <stdexcept>

namespace Core {

  struct FloatingPointException : public std::runtime_error {
    using std::runtime_error::runtime_error;//same constructors as base class
  };

  //A call to the following function will install a signal handler for SIGFPE
  //which will print diagnostics, and raise a FloatingPointException. Calling it
  //multiple times has no further effect.

  //NOTE: Calling it in release builds or on OSX has no effect.

  void catch_fpe();

  //For temporarily disabling FPE catching, use these two (after the above was
  //called):
  void disable_catch_fpe();
  void reenable_catch_fpe();

}

#endif
