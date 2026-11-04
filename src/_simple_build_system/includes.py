from . import utils
from . import langs
import pathlib

def create_include_decoder(exts):
    #decodes c++ include statements to look for possible includes to private header files (in same dir) or in libinc of own or other package.
    #
    #The decoder Returns (pkg,filename).
    #filename==None means not a valid match
    #pkg==None means possible private include, pkg!=None means possible include from that pkg
    import re
    exts = [(e.encode('ascii') if hasattr(e,'encode') else e) for e in exts]
    pattern = b'^\\s*#\\s*include\\s*"\\s*(([a-zA-Z0-9_]+/)?([a-zA-Z0-9_]+){1}(%s))\\s*"'%(b'|'.join(exts))
    #match=re.compile(pattern.encode('ascii') if hasattr(pattern,'encode') else pattern).match
    do_match=re.compile(pattern).match
    def decoder(ll):
        m = do_match(ll)
        if not m:
            return None,None
        _,pkg,fn,ext = m.groups()
        fn=b'%s%s'%(fn,ext)
        if pkg:
            pkg=pkg[:-1]
        return pkg,fn
    return decoder
include_decoder = create_include_decoder(langs.hdrext2lang.keys())

def _parse_includemap_txt_file( path ):
    with path.open('rt') as fh:
        for line in fh:
            line = line.split()
            if not line:
                continue
            k,v = line
            yield k,v

_cache_edm2im = {}
def _load_includemap_from_file( path_str ):
    res = _cache_edm2im.get(path_str)
    if res is None:
        res = {}
        for k,v in _parse_includemap_txt_file(pathlib.Path(path_str)):
            res[k] = v
        _cache_edm2im[path_str] = res
    return res

def _raw_construct_includemap_list( extdeps ):
    from . import env
    assert env.env is not None
    ei = env.env['extdeps']
    res = []
    for extdep in extdeps:
        im = ei[extdep].get('includemap')
        im = _load_includemap_from_file( im ) if im else None
        if im:
            res.append( ( extdep, im ) )
    return res

_cache_ed2il = {}
def _construct_includemap_list( extdep_set ):
    key = tuple( sorted(extdep_set) )
    res = _cache_ed2il.get(key)
    if res is None:
        res = _raw_construct_includemap_list( key )
        _cache_ed2il[key] = res
        assert res is not None
    return res

#For files with includes mapped by extdep include maps, the origin of each
#mapped package include, (pkgname,filename) -> (rawinclude,extdepname):
_mapped_origins = {}

def find_includes( cfile, pkg ):
    #We only look for includes which might be to files in same dir or other
    #packages, i.e. those using "../.." or "..", not <> or "../../.."
    #
    #We might find a few too many if there are ifdefs or /*..*/  style comments
    #(the scan does not evaluate preprocessor conditions, so all include
    #statements found are considered). Include statements with the marker
    #sbld::nodep (typically in a comment like "// sbld::nodep") are ignored.
    #
    includemap_list = _construct_includemap_list(pkg.extdeps())

    if includemap_list:
        #Extract raw includes, and then perform the mapping as appropriate.
        from .extdep_includemap import read_text_mapped_include_statements
        output, origins = read_text_mapped_include_statements( pathlib.Path(cfile),
                                                               includemap_list )
        output = output.encode('utf8')
        _mapped_origins[str(cfile)] = dict(
            ( _decode_pkginc( mapped ), origin )
            for mapped, origin in origins.items() if _decode_pkginc( mapped ) )
    else:
        output = [ line for line in utils.include_candidate_lines( cfile )
                   if b'sbld::nodep' not in line ]
        if not output:
            return None, None
    possible_privincs=set()
    possible_pkgincs=set()
    def bytes2str( b ):
        return b.decode('ascii')
    for ll in ( output.splitlines() if isinstance(output,bytes) else output ):
        pkgname,fn = include_decoder(ll)
        if fn:
            if pkgname:
                possible_pkgincs.add((bytes2str(pkgname),bytes2str(fn)))
            else:
                possible_privincs.add(bytes2str(fn))
    if pkg.extra_include_deps:
        from os.path import relpath
        rp=relpath(cfile,pkg.dirname)
        for fn0,incdep in pkg.extra_include_deps:
            if fn0==rp:
                pkgname,fn = include_decoder(
                    b'#include "%s"'%(incdep.encode('ascii')
                                      if hasattr(incdep,'encode') else incdep)
                )
                if fn:
                    if pkgname:
                        possible_pkgincs.add((bytes2str(pkgname),bytes2str(fn)))
                    else:
                        possible_privincs.add(bytes2str(fn))
    return possible_privincs,possible_pkgincs

def _decode_pkginc( inc ):
    #"Pkg/file.hh" -> ("Pkg","file.hh"), or None
    pkgname,fn = include_decoder( b'#include "%s"'%inc.encode('utf8') )
    if not fn or not pkgname:
        return None
    return pkgname.decode('ascii'), fn.decode('ascii')

def check_mapped_includes( pkg, cfiles, untracked ):
    #cfiles is a list of (path,description) of the files containing the
    #includes.
    """Error if any of the package includes in untracked, which will not be
    dependency-tracked (since they are not headers of the package itself or of
    its dependencies), come from an extdep include map. Such includes are still
    found by the compiler via the include directories of the extdep, so
    changes to them would otherwise silently not trigger rebuilds."""
    if not untracked:
        return
    for cfile, srcdescr in cfiles:
        origins = _mapped_origins.get( str(cfile) )
        if not origins:
            continue
        for p,f in sorted(untracked):
            origin = origins.get( (p,f) )
            if not origin:
                continue
            raw, extdep = origin
            from . import error
            import textwrap
            if p == pkg.name or p in pkg.deps_names():
                problem = f'but package {p} has no header file named "{f}"'
                advice = 'Fix the include map, or remove the include'
            else:
                problem = f'but {pkg.name} does not depend on a package named {p}'
                advice = ( f'Add {p} to the USEPKG list in {pkg.name}/pkg.info,'
                           ' fix the include map, or remove the include' )
            msg = ( f'{srcdescr} includes "{raw}", which the include map'
                    f' of extdep {extdep} translates to "{p}/{f}", {problem}.'
                    ' Such includes are not dependency-tracked, so changes'
                    f' to the header would not trigger rebuilds. {advice}.'
                    ' If the include is intentionally not a dependency'
                    ' (e.g. inside an #ifdef), mark it with a'
                    ' "// sbld::nodep" comment on the same line.' )
            #(keep the marker on a single line):
            _marker, _tmp = '// sbld::nodep', '//\x00sbld::nodep'
            lines = textwrap.wrap( msg.replace( _marker, _tmp ), width = 70,
                                   break_long_words = False,
                                   break_on_hyphens = False )
            error.error( '\n'.join( lines ).replace( _tmp, _marker ) )
