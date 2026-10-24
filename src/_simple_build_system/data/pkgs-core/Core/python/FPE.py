"""Control the catching of floating point exceptions (FPE), which is enabled in
debug builds (see Core/FPE.hh)."""

from ._fpe import catch_fpe, disable_catch_fpe, reenable_catch_fpe

__all__ = [ 'catch_fpe', 'disable_catch_fpe', 'reenable_catch_fpe',
            'DisableFPEContextManager' ]

class DisableFPEContextManager:
    """Context manager which disables the catching of floating point
    exceptions within its context."""

    def __enter__( self ):
        disable_catch_fpe()

    def __exit__( self, exc_type, exc_value, traceback ):
        reenable_catch_fpe()
