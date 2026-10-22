#Control all print operations, to guarantee nothing untowards gets printed if
#e.g. running --quiet or --env-setup.:

print_prefix_name = 'sbld'
print_prefix = f'{print_prefix_name}: '
_quiet = [False]#might be overridden by a call to make_quiet
_verbose = [False]#might be overridden by a call to make_verbose/make_quiet
_orig_printfct = print
_printfct = [_orig_printfct]
def print( *args, **kwargs ):
    return _printfct[0]( print_prefix, *args, **kwargs )
def print_no_prefix( *args, **kwargs ):
    return _printfct[0]( *args, **kwargs )
def raw_print_ignore_quiet( *args, **kwargs ):
    return _orig_printfct( *args, **kwargs )
def print_error( *args, **kwargs ):
    """Like print(), but for error messages, which must never be silenced:
    in quiet mode they are printed on stderr instead."""
    if _quiet[0]:
        import sys
        return _orig_printfct( print_prefix, *args, file = sys.stderr, **kwargs )
    return print( *args, **kwargs )
def make_quiet():
    if not _quiet[0]:
        _quiet[0] = True
        _printfct[0] = lambda *args, **kwargs : None
def make_verbose():
    _verbose[0] = True
def is_quiet():
    return _quiet[0]
def is_verbose():
    return _verbose[0] and not _quiet[0]
