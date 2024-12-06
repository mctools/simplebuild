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
            res.append(im)
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

def find_includes( cfile, pkg ):
    #We only look for includes which might be to files in same dir or other
    #packages, i.e. those using "../.." or "..", not <> or "../../.."
    #
    #We might find a few too many if there are ifdefs or /*..*/  style comments.
    #
    includemap_list = _construct_includemap_list(pkg.extdeps())

    if includemap_list:
        #Extract raw includes, and then perform the mapping as appropriate.
        from .extdep_includemap import read_text_mapped_include_statements
        output = read_text_mapped_include_statements( pathlib.Path(cfile),
                                                      includemap_list )
        output = output.encode('utf8')
    else:
        #For efficiency, initial dig through file use grep command:
        ec,output=utils.run(['grep','.*#.*include.*"..*"',cfile])
        if ec == 1:
            #grep exit code of 1 simply indicates no hits
            return None, None
        if ec!=0:
            raise RuntimeError('grep command failed')
    possible_privincs=set()
    possible_pkgincs=set()
    def bytes2str( b ):
        return b.decode('ascii')
    for ll in output.splitlines():
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
