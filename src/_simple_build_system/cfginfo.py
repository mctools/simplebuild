# Information about the simplebuild configuration of the selected build variant,
# collected into a single JSON-compatible dictionary. This dictionary is the
# basis of all ways to inspect the configuration (sb --summary, sb --showcfg,
# and the simplebuild.cfg Python module installed by each build), so they all
# provide the same information.

#Name of the file in the install directory with the dictionary (written by
#each build):
installed_filename = 'cfginfo.json'

summary_formats = ( 'text', 'json' )

from .singlecfg import reserved_bundle_name # noqa: E402

def _pathstr( p ):
    return None if p is None else str( p )

def _bundle_roots():
    import pathlib
    from . import envcfg
    res = []
    for name, cfgfile, pkg_root, is_main in envcfg.var.bundles:
        res.append( ( pathlib.Path( pkg_root ).absolute(), name ) )
    return res

def bundle_of_pkg( pkg ):
    """Name of the bundle providing the package."""
    import pathlib
    basedir = pathlib.Path( pkg.basedir ).absolute()
    for pkg_root, name in _bundle_roots():
        if pkg_root == basedir:
            return name or reserved_bundle_name
    #Fall back to comparing resolved paths:
    basedir = basedir.resolve()
    for pkg_root, name in _bundle_roots():
        if pkg_root.resolve() == basedir:
            return name or reserved_bundle_name
    return None

def _load_pkgs():
    from . import loadpkgs
    from . import dirs
    from . import conf
    from . import envcfg
    return loadpkgs.PackageLoader( loadpkgs.find_pkg_dirs( dirs.pkgsearchpath ),
                                   envcfg.var.pkg_filter,
                                   autodeps = conf.autodeps,
                                   load_all = True )

def collect( *, envdict = None, pkgloader = None ):
    """Collect the information into a JSON-compatible dictionary. The envdict
    is the result of the CMake inspection of the environment (by default
    loaded from the cache, if available), and the pkgloader a
    loadpkgs.PackageLoader object (by default created by loading the pkg.info
    files of all packages)."""
    from . import envcfg
    from . import dirs
    var = envcfg.var
    vflags = var.variant_flags

    if envdict is None:
        from .backend import load_envcache
        envdict = load_envcache()

    d = {}
    d['main_cfg_file'] = str( var.main_cfg_file_resolved )
    #(an unnamed main bundle is referred to as "main", which is a reserved
    #bundle name):
    d['bundles'] = [ dict( name = name or reserved_bundle_name,
                           cfgfile = _pathstr( cfgfile ),
                           pkg_root = _pathstr( pkg_root ),
                           main = bool( is_main ) )
                     for name, cfgfile, pkg_root, is_main in var.bundles ]
    d['pkgsearchpath'] = [ str(e) for e in dirs.pkgsearchpath ]

    if pkgloader is None:
        pkgloader = _load_pkgs()
        if envdict is not None:
            #Packages with missing external dependencies will be disabled:
            _missing = set( k for k,v in envdict['extdeps'].items()
                            if not v['present'] )
            if _missing:
                pkgloader.disable_pkgs_with_extdeps( _missing )
    d['packages'] = dict( total = len( pkgloader.pkgs ),
                          enabled = sum( 1 for p in pkgloader.pkgs if p.enabled ),
                          filter = list( var.build_pkg_filter ) )

    if vflags.ignore_extra_flags:
        flags_from = '-x'
    elif vflags.flagset:
        flags_from = '-X'
    else:
        flags_from = 'cfg'
    d['build'] = dict(
        mode = var.build_mode,
        mode_from = vflags.mode_flag() or 'cfg',
        cfg_mode = var.cfg_build_mode,
        extra_cflags = list( var.extra_cflags ),
        extra_ldflags = list( var.extra_ldflags ),
        extra_flags_from = flags_from,
        flagset = var.flagset,
        flagsets = dict( ( name, dict( extra_cflags = list(cf),
                                       extra_ldflags = list(lf) ) )
                         for name, (cf, lf)
                         in sorted( var.cfg_build_flagsets.items() ) ),
        max_cachedirs = var.build_max_cachedirs )

    v = dict( flags = vflags.as_args(),
              cachedir = str( var.build_cachedir ),
              blddir = str( dirs.blddir ),
              installdir = str( dirs.installdir ) )
    d['variant'] = v

    if envdict is None:
        d['extdeps'] = None
    else:
        #External dependencies which are not used by any of the enabled
        #packages are not checked (and therefore never present, unless
        #activated by another external dependency):
        _used = envdict['_actually_needed_extdeps']
        def _extdep( name, info ):
            e = dict( present = bool( info.get('present') ),
                      used = name in _used )
            if e['present']:
                e['version'] = info.get('version') or None
            return e
        d['extdeps'] = dict( ( k, _extdep(k,info) )
                             for k, info in sorted( envdict['extdeps'].items() ) )
    return d

#Keys of the text summary, which are also accepted by --showcfg (in addition to
#the key paths of the dictionary itself):

def _summary_items( d ):
    """List of (key, value) for the text summary. The values are str, None,
    or lists of str."""
    b = d['build']
    v = d['variant']
    items = [
        ( 'main_cfg_file', d['main_cfg_file'] ),
        ( 'bundles', [ e['name'] for e in d['bundles'] ] ),
        ( 'pkgsearchpath', d['pkgsearchpath'] ),
        ( 'packages.total', d['packages']['total'] ),
        ( 'packages.enabled', d['packages']['enabled'] ),
        ( 'packages.filter', d['packages']['filter'] ),
        ( 'build.mode', b['mode'] ),
        ( 'build.mode_from', b['mode_from'] ),
        ( 'build.extra_cflags', b['extra_cflags'] ),
        ( 'build.extra_ldflags', b['extra_ldflags'] ),
        ( 'build.extra_flags_from', b['extra_flags_from'] ),
        ( 'build.flagset', b['flagset'] ),
        ( 'build.flagsets', list( b['flagsets'].keys() ) ),
        ( 'build.max_cachedirs', b['max_cachedirs'] ),
        ( 'variant.flags', v['flags'] ),
        ( 'variant.blddir', v['blddir'] ),
        ( 'variant.installdir', v['installdir'] ),
    ]
    ed = d['extdeps']
    if ed is None:
        for k in ( 'present', 'missing', 'unused' ):
            items.append( ( f'extdeps.{k}', None ) )
    else:
        def _fmt( k, e ):
            ver = e.get('version')
            return f'{k} {ver}' if ver and ver != '-' else k
        items.append( ( 'extdeps.present', [ _fmt( k, e ) for k, e in ed.items()
                                             if e['present'] ] ) )
        items.append( ( 'extdeps.missing', [ k for k, e in ed.items()
                                             if not e['present'] and e['used'] ] ) )
        items.append( ( 'extdeps.unused', [ k for k, e in ed.items()
                                            if not e['present'] and not e['used'] ] ) )
    return items

def _valstr( v ):
    if v is None or v == {}:
        return ''
    if isinstance( v, bool ):
        return 'true' if v else 'false'
    return str( v )

def _format_lines( items ):
    """Aligned "KEY : VALUE" lines, with list values continuing on the
    following lines."""
    w = max( len(k) for k, _ in items ) if items else 0
    lines = []
    for k, v in items:
        vals = v if isinstance( v, list ) else [ v ]
        vals = [ _valstr(e) for e in vals ] or [ '' ]
        lines.append( f'{k.ljust(w)} : {vals[0]}'.rstrip() )
        for e in vals[1:]:
            lines.append( f'{"".ljust(w)}   {e}'.rstrip() )
    return lines

def format_text( d ):
    lines = _format_lines( _summary_items( d ) )
    if d['extdeps'] is None:
        lines.append( '' )
        lines.append( 'The external dependencies are not yet known'
                      ' (run "sb -s -e" to inspect them).' )
    return '\n'.join( lines ) + '\n'

def format_json( d ):
    import json
    return json.dumps( d, indent = 2 ) + '\n'

def _flatten( prefix, v ):
    #Leaf (key, value) items of a dictionary:
    if isinstance( v, dict ) and v:
        res = []
        for k, e in v.items():
            res += _flatten( f'{prefix}.{k}' if prefix else k, e )
        return res
    if isinstance( v, list ) and v and any( isinstance( e, dict ) for e in v ):
        res = []
        for i, e in enumerate( v ):
            res += _flatten( f'{prefix}.{i}', e )
        return res
    return [ ( prefix, v ) ]

def valid_keys( d ):
    """The keys accepted by lookup, in the order of the text summary followed
    by the leaf key paths of the dictionary."""
    res = [ k for k, _ in _summary_items( d ) ]
    seen = set( res )
    for k, _ in _flatten( '', d ):
        if k not in seen:
            seen.add( k )
            res.append( k )
    return res

def _lookup_path( d, key ):
    #Look up a dotted key path in the dictionary. Returns (found, value).
    v = d
    for part in key.split('.'):
        if isinstance( v, dict ) and part in v:
            v = v[part]
        elif isinstance( v, list ) and part.isdigit() and int(part) < len(v):
            v = v[int(part)]
        else:
            return False, None
    return True, v

def lookup( d, key ):
    """Text output for a single key (lines without the key for simple values
    and lists, aligned KEY : VALUE lines for sub-tables). Returns None if the
    key is not valid."""
    summary = dict( _summary_items( d ) )
    if key in summary:
        v = summary[key]
    else:
        found, v = _lookup_path( d, key )
        if not found:
            return None
    if isinstance( v, dict ) or ( isinstance( v, list )
                                  and any( isinstance(e,dict) for e in v ) ):
        items = _flatten( key, v )
        return '\n'.join( _format_lines( items ) ) + '\n'
    vals = v if isinstance( v, list ) else [ v ]
    return ''.join( _valstr(e) + '\n' for e in vals )

def decode_summary_format( fmt, parser ):
    """Decode the FORMAT given to -s/--summary (also allowing -s=FORMAT)."""
    if fmt.startswith('='):
        fmt = fmt[1:]
    if fmt not in summary_formats:
        parser.error( f'Invalid format "{fmt}" for --summary (valid formats'
                      f' are: {", ".join(summary_formats)})' )
    return fmt

#The overview of the cache directories of all build variants at the end of the
#text summary of sb -s. This is not part of the dictionary above, since it is
#not part of the configuration (and changes with each build).

def _disk_usage( paths ):
    #Size on disk of the files in the directories (symlinks are not followed,
    #and hard links are only counted once):
    import os
    seen, n = set(), 0
    for p in paths:
        for root, dirnames, filenames in os.walk( p ):
            for f in filenames + dirnames:
                try:
                    st = os.lstat( os.path.join( root, f ) )
                except OSError:
                    continue
                if ( st.st_dev, st.st_ino ) in seen:
                    continue
                seen.add( ( st.st_dev, st.st_ino ) )
                n += getattr( st, 'st_blocks', 0 ) * 512 or st.st_size
    return n

def _fmt_size( n ):
    for unit in ( 'B', 'kB', 'MB', 'GB' ):
        if n < 1000.0 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1000.0

def flagset_names( cd ):
    """Names of the flag sets in the cfg file with the extra flags used in the
    cache dir (a cachedirs.CacheDir object)."""
    from . import envcfg
    flags = cd.extra_flags()
    if not flags or flags == ( (), () ):
        return []
    return sorted( n for n, fs in envcfg.var.cfg_build_flagsets.items()
                   if tuple( tuple(e) for e in fs ) == flags )

def format_cachedirs():
    """Overview of the cache directories of all build variants, with the
    names of matching flag sets (for -X) first."""
    from . import envcfg
    from . import dirs
    from . import cachedirs
    var = envcfg.var
    cds = cachedirs.find_cachedirs( var.build_cachedir )
    if not cds:
        return ''
    rows = []
    for cd in cds:
        flags = cd.extra_flags()
        if flags is None:
            fsnames, descr = '', cd.name()
        else:
            fsnames = ','.join( flagset_names( cd ) )
            descr = ' '.join( [ cd.mode() ]
                              + [ f'{k}={" ".join(v)}' for k, v
                                  in zip( ( 'extra_cflags', 'extra_ldflags' ), flags )
                                  if v ] )
        size = _fmt_size( _disk_usage( [ cd.blddir, cd.installdir ] ) )
        rows.append( ( fsnames, descr, size,
                       'current' if cd.blddir == dirs.blddir else '' ) )
    rows.sort( key = lambda r : ( r[0] == '', r[0], r[1] ) )
    w0 = max( len(r[0]) for r in rows )
    w1 = max( len(r[1]) for r in rows )
    w2 = max( len(r[2]) for r in rows )
    lines = [ f'Cache directories in {var.build_cachedir}:' ]
    for r in rows:
        cols = ( [ r[0].ljust(w0) ] if w0 else [] ) + [ r[1].ljust(w1),
                                                        r[2].rjust(w2), r[3] ]
        lines.append( ( '  ' + '  '.join( cols ) ).rstrip() )
    return '\n'.join( lines ) + '\n'
