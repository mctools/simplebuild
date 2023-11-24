# Error/warning functions and classes to distinguish exceptions thrown by our
# code from other exceptions.
#
# Typical intended usage:
#
# from . import error
# error.error('some error message')
# error.warn('some warning message')
#
# IMPORTANT: This module should NOT import other simplebuild modules (in
# particular not anything triggering envcfg etc.)

import warnings

class Error(Exception):
    pass

class SimpleBuildUserWarning( UserWarning ):
    """UserWarning's emitted from simplebuild"""
    def __init__(self,*args,**kwargs):
        super(SimpleBuildUserWarning, self).__init__(*args,**kwargs)

default_error_type = SystemExit

def error(*args):
    raise default_error_type('ERROR: '+'\n'.join(args))

#Used to exit the programme after catching and dealing with an Error at a lower level.
class CleanExit(Exception):
    pass
def clean_exit(ec):
    ce=CleanExit()
    ce._the_ec=ec
    raise ce

def print_traceback(exc):
    from .io import print
    print()
    import traceback
    print("----begin traceback---")
    if hasattr(exc,'__traceback__'):
        traceback.print_exception(type(exc),exc,exc.__traceback__)
    else:
        #This can only happen in python2:
        traceback.print_exc(exc)
    print("----end traceback---")
    print()


def direct_print_warning( msg ):
    from .io import print_prefix,print_prefix_name,print_no_prefix
    s = print_prefix.replace(print_prefix_name, '%s WARNING'%print_prefix_name)
    print_no_prefix('%s%s'%(s,msg))

_orig_showwarning = warnings.showwarning
def _custom_warning_fmt(msg,cat,*args,**kwargs):
    if issubclass(cat,SimpleBuildUserWarning):
        direct_print_warning( msg )
    else:
        _orig_showwarning(msg,cat,*args,**kwargs)

def fmt_simplebuild_warnings():
    warnings.showwarning = _custom_warning_fmt

def warn(msg):
    warnings.warn( SimpleBuildUserWarning( str(msg) ), stacklevel = 2 )
