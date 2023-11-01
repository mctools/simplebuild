# Custom Exception class to distinguish exceptions thrown by our code from other exceptions.
#
# Intended usage:
#
# from . import error
# error.error('some error message')


# IMPORTANT: This module should NOT import other simplebuild modules (in particular
# not anything triggering envcfg etc.)

import warnings

class Error(Exception):
    pass

class SimpleBuildUserWarning( UserWarning ):
    """UserWarning's emitted from simplebuild"""
    def __init__(self,*args,**kwargs):
        super(SimpleBuildUserWarning, self).__init__(*args,**kwargs)

default_error_type = SystemExit

def error(*args):
    raise default_error_type('\n'.join(args))

#Used to exit the programme after catching and dealing with an Error at a lower level.
class CleanExit(Exception):
    pass
def clean_exit(ec):
    ce=CleanExit()
    ce._the_ec=ec
    raise ce

def print_traceback(exc,prefix=''):
    print (prefix)
    import traceback
    print ("%s----begin traceback---"%prefix)
    if hasattr(exc,'__traceback__'):
        traceback.print_exception(type(exc),exc,exc.__traceback__)
    else:
        #This can only happen in python2:
        traceback.print_exc(exc)
    print ("%s----end traceback---"%prefix)
    print (prefix)


_orig_showwarning = warnings.showwarning
def _custom_warning_fmt(msg,cat,*args,**kwargs):
    if issubclass(cat,SimpleBuildUserWarning):
        print('simplebuild WARNING: %s'%msg)
    else:
        _orig_showwarning(msg,cat,*args,**kwargs)

def fmt_simplebuild_warnings():
    warnings.showwarning = _custom_warning_fmt

def warn(msg):
    warnings.warn( SimpleBuildUserWarning( str(msg) ), stacklevel = 2 )
