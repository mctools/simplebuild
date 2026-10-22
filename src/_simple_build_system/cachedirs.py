# Management of the cache directories of the various build variants (see
# variant.py). Each variant has a pair of directories (bld<suffix> and
# install<suffix>) inside the build.cachedir directory, and this is what we
# refer to as a "cache dir" in this module.
#
# Be careful with imports in this file, it is used in the startup of sbrun and
# sbenv.

import re

_reobj_cachedir_name = re.compile(
    r'^(bld|install)((_debug|_reldbg)?(_xf[0-9a-f]{10})?)$' )

last_used_filename = 'last_used.touch'
extra_flags_filename = 'extra_flags.txt'

def touch_last_used( blddir, create_missing = True ):
    """Mark the cache dir as used (for the purpose of removing the least
    recently used ones)."""
    if not create_missing and not blddir.is_dir():
        return
    try:
        ( blddir / last_used_filename ).touch()
    except OSError:
        pass#Never fail for this

class CacheDir:

    def __init__( self, cachedir, suffix ):
        self.suffix = suffix
        self.blddir = cachedir / f'bld{suffix}'
        self.installdir = cachedir / f'install{suffix}'

    def name( self ):
        return f'bld{self.suffix}+install{self.suffix}'

    def last_used( self ):
        for f in ( self.blddir / last_used_filename,
                   self.blddir, self.installdir ):
            try:
                return f.stat().st_mtime
            except OSError:
                pass
        return 0.0

    def is_locked( self ):
        #Stale locks (from processes which no longer exist) do not count:
        from .lockfile import is_locked
        return is_locked( self.blddir / '.lock' )

    def can_remove( self ):
        #Only remove directories with the expected fingerprint files, to avoid
        #accidentally removing any user data:
        for d, fp in ( ( self.blddir, '.sbbuilddir' ),
                       ( self.installdir, '.sbinstalldir' ) ):
            if ( d.exists() or d.is_symlink() ) and (
                    d.is_symlink() or not d.is_dir()
                    or not ( d / fp ).exists() ):
                return False
        return True

    def remove( self ):
        from . import utils
        assert self.can_remove()
        #Remove the build dir last, since that is where the lockfile is:
        for d in ( self.installdir, self.blddir ):
            utils.remove_cache_dir( d )

def find_cachedirs( cachedir ):
    """Find the cache dirs of all variants in the cachedir."""
    suffixes = set()
    if cachedir.is_dir():
        for f in cachedir.iterdir():
            m = _reobj_cachedir_name.match( f.name )
            if m:
                suffixes.add( m.group(2) )
    return [ CacheDir( cachedir, s ) for s in sorted(suffixes) ]

def remove_least_recently_used( cachedir, current_blddir, max_cachedirs ):
    """Remove the least recently used cache dirs, so at most max_cachedirs
    remain. The cache dir in current use is never removed, nor any cache dir
    which is locked by a running sb process or which can not be safely
    removed. Returns the removed CacheDir objects."""
    #Directories which do not look like they were created by simplebuild are
    #not counted (but locked ones are, since they are actually in use):
    others = [ cd for cd in find_cachedirs( cachedir )
               if cd.blddir != current_blddir and cd.can_remove() ]
    n_excess = len(others) + 1 - max_cachedirs
    removed = []
    if n_excess <= 0:
        return removed
    for cd in sorted( others, key = lambda cd : cd.last_used() ):
        if len(removed) >= n_excess:
            break
        if cd.is_locked():
            continue
        cd.remove()
        removed.append( cd )
    return removed

def remove_all( cachedir, current_blddir ):
    """Remove all cache dirs, except those locked by another running sb process
    or which can not be safely removed. Returns (removed, skipped) lists of
    CacheDir objects."""
    removed, skipped = [], []
    for cd in find_cachedirs( cachedir ):
        if ( ( cd.blddir != current_blddir and cd.is_locked() )
             or not cd.can_remove() ):
            skipped.append( cd )
            continue
        cd.remove()
        removed.append( cd )
    return removed, skipped

#File in the cache directory (the parent of the bld* and install* dirs)
#recording the full path of the simplebuild.cfg file of the bundle using it:
cfgpath_filename = 'simplebuild_cfg_path.txt'

def read_cachedir_owner( cachedir ):
    """The path to the simplebuild.cfg file recorded in the cache directory
    (or None if not recorded)."""
    try:
        return ( cachedir / cfgpath_filename ).read_text().strip() or None
    except (OSError,UnicodeDecodeError):
        return None

def record_cachedir_owner( cachedir, cfgfile ):
    """Record the path to the simplebuild.cfg file in the cache directory, for
    the benefit of humans and to detect clashes."""
    from .utils import write_atomic
    if read_cachedir_owner( cachedir ) != str(cfgfile):
        write_atomic( cachedir / cfgpath_filename, f'{cfgfile}\n' )

def write_extra_flags_file( blddir, extra_cflags, extra_ldflags ):
    """Record the extra flags used in a given cache dir, for the benefit of
    humans inspecting the cache directory."""
    f = blddir / extra_flags_filename
    content = ( 'Extra flags from the simplebuild cfg file used for the'
                ' build in this directory:\n\n'
                f'extra_cflags: {" ".join(extra_cflags)}\n'
                f'extra_ldflags: {" ".join(extra_ldflags)}\n' )
    if not f.exists() or f.read_text() != content:
        f.write_text( content )
