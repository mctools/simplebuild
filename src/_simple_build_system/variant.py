# Selection of the build variant (build mode, and whether to use the extra
# flags from the simplebuild cfg file, a named flag set from the cfg file, or no
# extra flags) via command line flags. This must
# happen before the envcfg module is imported, since that is where the cache
# directories of the selected variant are determined.
#
# The same short flags are supported by sb, sbrun, and sbenv:
#
#   -d : build mode 'debug' (ignore build.mode from cfg file)
#   -r : build mode 'release' (ignore build.mode from cfg file)
#   -g : build mode 'reldbg' (ignore build.mode from cfg file)
#   -x : ignore build.extra_cflags and build.extra_ldflags from cfg file
#   -X NAME : use the extra flags of the flag set NAME from the
#             build.flagsets table of the cfg file (instead of
#             build.extra_cflags and build.extra_ldflags)
#
# Be careful with imports in this file, it is used in the startup of sbrun and
# sbenv.

_mode_flags = { 'd' : 'debug', 'r' : 'release', 'g' : 'reldbg' }

class VariantFlags:

    def __init__( self, mode = None, ignore_extra_flags = False, flagset = None ):
        assert mode is None or mode in _mode_flags.values()
        assert not ( ignore_extra_flags and flagset )
        self.mode = mode
        self.ignore_extra_flags = bool(ignore_extra_flags)
        self.flagset = flagset or None

    def mode_flag( self ):
        """The command line flag used to select the mode (or None)."""
        if self.mode is None:
            return None
        return '-' + next( k for k,v in _mode_flags.items() if v == self.mode )

    def as_args( self ):
        """The command line flags selecting this variant."""
        res = []
        if self.mode:
            res.append( self.mode_flag() )
        if self.ignore_extra_flags:
            res.append( '-x' )
        if self.flagset:
            res += [ '-X', self.flagset ]
        return res

_selected = [ None ]

def select( variant_flags ):
    import sys
    if ( __package__ + '.envcfg' ) in sys.modules:
        raise RuntimeError('variant.select called too late (envcfg already loaded)')
    assert isinstance( variant_flags, VariantFlags )
    _selected[0] = variant_flags

def selected():
    return _selected[0] or VariantFlags()

def add_argparse_options( parser_or_group ):
    """Add the variant flags to an argparse (group) object. Only short options
    are provided."""
    g = parser_or_group.add_mutually_exclusive_group()
    g.add_argument( '-d', action='store_const', dest='variant_mode',
                    const='debug',
                    help="Use build mode 'debug' (overriding build.mode).")
    g.add_argument( '-r', action='store_const', dest='variant_mode',
                    const='release',
                    help="Use build mode 'release' (overriding build.mode).")
    g.add_argument( '-g', action='store_const', dest='variant_mode',
                    const='reldbg',
                    help="Use build mode 'reldbg' (overriding build.mode).")
    gx = parser_or_group.add_mutually_exclusive_group()
    gx.add_argument(
        '-x', action='store_true', dest='variant_ignore_extra_flags',
        help=( 'Ignore build.extra_cflags and build.extra_ldflags.' ) )
    gx.add_argument(
        '-X', metavar='NAME', dest='variant_flagset',
        help=( 'Use the extra flags of the flag set NAME in build.flagsets'
               ' (instead of build.extra_cflags and build.extra_ldflags).' ) )

def from_argparse_result( args ):
    if args.variant_flagset is not None and not is_valid_flagset_name( args.variant_flagset ):
        from .error import error
        error(f'Invalid flag set name "{args.variant_flagset}" given to -X (names can only contain'
              ' letters, digits, underscores and dashes, and can not start with a dash)')
    return VariantFlags( mode = args.variant_mode,
                         ignore_extra_flags = args.variant_ignore_extra_flags,
                         flagset = args.variant_flagset )

def fast_parse_leading_flags( args ):
    """Efficiently parse leading flags (all arguments before the first one not
    starting with '-') for the simple and common valid cases. Returns
    (VariantFlags, remaining_args), or None if the arguments must instead be
    parsed by argparse (help requests, invalid flags, conflicting modes,
    missing program, ...)."""
    mode = None
    ignore_extra_flags = False
    flagset = None
    i = 0
    n = len(args)
    while i < n:
        a = args[i]
        if not a.startswith('-'):
            break
        if len(a) < 2:
            return None
        for j,c in enumerate(a[1:],start=1):
            if c == 'x':
                ignore_extra_flags = True
            elif c == 'X':
                #The name is the rest of the argument or the next argument:
                if flagset is not None:
                    return None
                if j + 1 < len(a):
                    flagset = a[j+1:]
                else:
                    i += 1
                    if i == n:
                        return None
                    flagset = args[i]
                if not is_valid_flagset_name( flagset ):
                    return None
                break
            else:
                m = _mode_flags.get(c)
                if m is None or ( mode is not None and mode != m ):
                    return None
                mode = m
        i += 1
    if i == n:
        return None#no program
    if ignore_extra_flags and flagset:
        return None
    return VariantFlags( mode, ignore_extra_flags, flagset ), args[i:]

#Names of the build modes can not be used as names of flag sets (to avoid
#confusion, since modes and flag sets can be combined):
reserved_flagset_names = tuple( _mode_flags.values() )

def is_valid_flagset_name( name ):
    """Names of flag sets must be non-empty and contain only letters, digits,
    underscores and dashes (not starting with a dash)."""
    import re
    return bool( re.fullmatch( r'[A-Za-z0-9_][A-Za-z0-9_-]*', name ) )

def parse_launcher_args( progname, args, description ):
    """Parse args of sbenv/sbrun, which are on the form: [flags] <program>
    [args]. Returns (VariantFlags, program_and_args)."""
    res = fast_parse_leading_flags( args )
    if res is not None:
        return res
    #Not the simple case, so use argparse for proper help and error messages
    #(but still only consider leading arguments as flags):
    import argparse
    i = 0
    while i < len(args) and args[i].startswith('-'):
        if args[i].endswith('X') and not args[i].startswith('--'):
            i += 1#the next argument is the name of the flag set
        i += 1
    i = min( i, len(args) )
    parser = argparse.ArgumentParser(
        prog = progname,
        usage = f'{progname} [-h] [-d|-r|-g] [-x|-X NAME] <program> [args]',
        description = description,
        formatter_class = argparse.RawDescriptionHelpFormatter,
        allow_abbrev = False )
    add_argparse_options( parser )
    parser.add_argument( 'program', nargs='?', help = argparse.SUPPRESS )
    opt = parser.parse_args( args[:i] )
    if i == len(args):
        parser.error('missing program to run')
    return from_argparse_result( opt ), args[i:]

def cachedir_suffix( mode, extra_cflags, extra_ldflags ):
    """Suffix for the names of the bld and install directories of a given
    variant. Variants without extra flags use the same names as simplebuild
    always did (e.g. 'bld' and 'install_debug')."""
    s = '' if mode == 'release' else f'_{mode}'
    if extra_cflags or extra_ldflags:
        s += '_xf' + extra_flags_hash( extra_cflags, extra_ldflags )
    return s

def extra_flags_hash( extra_cflags, extra_ldflags ):
    import hashlib
    import json
    data = json.dumps( [ list(extra_cflags), list(extra_ldflags) ] )
    return hashlib.sha256( data.encode() ).hexdigest()[:10]

def extra_flags_description( extra_cflags, extra_ldflags ):
    parts = []
    if extra_cflags:
        parts.append( 'extra_cflags: ' + ' '.join(extra_cflags) )
    if extra_ldflags:
        parts.append( 'extra_ldflags: ' + ' '.join(extra_ldflags) )
    return '  '.join(parts)
