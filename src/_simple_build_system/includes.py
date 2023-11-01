from . import utils
from . import langs

def create_include_decoder(exts):
    #decodes c++ include statements to look for possible includes to private header files (in same dir) or in libinc of own or other package.
    #
    #The decoder Returns (pkg,filename).
    #filename==None means not a valid match
    #pkg==None means possible private include, pkg!=None means possible include from that pkg
    import re
    exts = [(e.encode('ascii') if hasattr(e,'encode') else e) for e in exts]
    pattern = b'^\s*#\s*include\s*"\s*(([a-zA-Z0-9_]+/)?([a-zA-Z0-9_]+){1}(%s))\s*"'%(b'|'.join(exts))
    #match=re.compile(pattern.encode('ascii') if hasattr(pattern,'encode') else pattern).match
    match=re.compile(pattern).match
    def decoder(l):
        m=match(l)
        if not m:
            return None,None
        _,pkg,fn,ext = m.groups()
        fn=b'%s%s'%(fn,ext)
        if pkg:
            pkg=pkg[:-1]
        return pkg,fn
    return decoder
include_decoder = create_include_decoder(langs.hdrext2lang.keys())

def find_includes(cfile,pkg):
    #We only look for includes which might be to files in same dir or other packages, i.e.
    #those using "../.." or "..", not <> or "../../.."
    #
    #We might find a few too many if there are ifdefs or /*..*/  style comments.
    #
    #For efficiency, initial dig through file use grep command:
    ec,output=utils.run(['grep','.*#.*include.*"..*"',cfile])
    if ec!=0:
        return None,None
    possible_privincs=set()
    possible_pkgincs=set()
    def bytes2str( b ):
        return b.decode('ascii')
    for l in output.splitlines():
        pkgname,fn = include_decoder(l)
        if fn:
            if pkgname:
                possible_pkgincs.add((bytes2str(pkgname),bytes2str(fn)))
            else:
                possible_privincs.add(bytes2str(fn))
    if pkg.extra_include_deps:
        from os.path import relpath
        rp=relpath(cfile,pkg.dirname)#todo: this will have to be changed if we want to support dynamic packages (but perhaps we should rather obsolete the EXTRA_INCDEPS flag?)
        for fn0,incdep in pkg.extra_include_deps:
            if fn0==rp:
                pkgname,fn = include_decoder(b'#include "%s"'%(incdep.encode('ascii') if hasattr(incdep,'encode') else incdep))
                if fn:
                    if pkgname:
                        possible_pkgincs.add((bytes2str(pkgname),bytes2str(fn)))
                    else:
                        possible_privincs.add(bytes2str(fn))
    return possible_privincs,possible_pkgincs
