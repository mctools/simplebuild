# Selection of the build variant (build mode and whether or not to ignore any
# extra flags from the simplebuild cfg file) via command line flags. This must
# happen before the envcfg module is imported, since that is where the cache
# directories of the selected variant are determined.
#
# The same short flags are supported by sb, sbrun, and sbenv:
#
#   -d : build mode 'debug' (ignore build.mode from cfg file)
#   -r : build mode 'release' (ignore build.mode from cfg file)
#   -g : build mode 'reldbg' (ignore build.mode from cfg file)
#   -x : ignore build.extra_cflags and build.extra_ldflags from cfg file
#
# Be careful with imports in this file, it is used in the startup of sbrun and
# sbenv.

_mode_flags = { 'd' : 'debug', 'r' : 'release', 'g' : 'reldbg' }

class VariantFlags:

    def __init__( self, mode = None, ignore_extra_flags = False ):
        assert mode is None or mode in _mode_flags.values()
        self.mode = mode
        self.ignore_extra_flags = bool(ignore_extra_flags)

    def mode_flag( self ):
        """The command line flag used to select the mode (or None)."""
        if self.mode is None:
            return None
        return '-' + next( k for k,v in _mode_flags.items() if v == self.mode )

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
    parser_or_group.add_argument(
        '-x', action='store_true', dest='variant_ignore_extra_flags',
        help=( 'Ignore build.extra_cflags and build.extra_ldflags.' ) )

def from_argparse_result( args ):
    return VariantFlags( mode = args.variant_mode,
                         ignore_extra_flags = args.variant_ignore_extra_flags )

def fast_parse_leading_flags( args ):
    """Efficiently parse leading flags (all arguments before the first one not
    starting with '-') for the simple and common valid cases. Returns
    (VariantFlags, remaining_args), or None if the arguments must instead be
    parsed by argparse (help requests, invalid flags, conflicting modes,
    missing program, ...)."""
    mode = None
    ignore_extra_flags = False
    i = 0
    n = len(args)
    while i < n:
        a = args[i]
        if not a.startswith('-'):
            break
        if len(a) < 2:
            return None
        for c in a[1:]:
            if c == 'x':
                ignore_extra_flags = True
            else:
                m = _mode_flags.get(c)
                if m is None or ( mode is not None and mode != m ):
                    return None
                mode = m
        i += 1
    if i == n:
        return None#no program
    return VariantFlags( mode, ignore_extra_flags ), args[i:]

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
        i += 1
    parser = argparse.ArgumentParser(
        prog = progname,
        usage = f'{progname} [-h] [-d|-r|-g] [-x] <program> [args]',
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
