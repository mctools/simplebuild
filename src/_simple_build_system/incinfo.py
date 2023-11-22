import os
import pathlib
from . import utils
from . import langs
from . import col
from . import includes
from . import conf
from .grep import pkgdir_for_search
_ospath = os.path

ccxx_extensions = set(ext for ext,lang in langs.hdrext2lang.items() if lang in ('cxx','c'))
ccxx_extensions.update(set(ext for ext,lang in langs.srcext2lang.items() if lang in ('cxx','c')))

def ccxx_files_in_dir(d):
    out=[]
    for f in os.listdir(d):
        if not conf.ignore_file(f):
            if _ospath.splitext(f)[1] not in ccxx_extensions:
                continue
            f=_ospath.join(d,f)
            if _ospath.isdir(f):
                continue
            out+=[f]
    return out

def _printform(pkg,f,for_sortkey=False):
    f = pathlib.Path(f).parts[-3:]
    assert f[0]==pkg.name
    if for_sortkey:
        return tuple(f)
    return '%s%s/%s/%s%s'%(col.ok if pkg.enabled else col.bad,
                           f[0],f[1],f[2],col.end)

def _rel_description(f,f2):
    f=_ospath.dirname(f)
    f2=_ospath.dirname(f2)
    if f==f2:
        return ' %s(same directory)%s'%(col.inc_samedir,col.end)
    f=_ospath.dirname(f)
    f2=_ospath.dirname(f2)
    if f==f2:
        return ' %s(same package)%s'%(col.inc_samepkg,col.end)
    return ''

_cache_incs_direct={}
def _incs_direct(pkg,f):
    global _cache_incs_direct
    if f in _cache_incs_direct:
        return _cache_incs_direct[f]
    res={}
    possible_privincs,possible_pkgincs = includes.find_includes(f,pkg)
    d=_ospath.dirname(f)
    if possible_privincs:
        for p in possible_privincs:
            pp=_ospath.join(d,p)
            if _ospath.exists(pp) and pp!=f:
                res[_printform(pkg,pp,for_sortkey=True)] = (pkg,pp)
    if possible_pkgincs:
        deppkgs = dict((p.name,p) for p in pkg.deps())
        deppkgs[pkg.name]=pkg#also depend on ourselves here
        for ppkgname,p in possible_pkgincs:
            ppkg=deppkgs.get(ppkgname,None)
            if not ppkg:
                continue
            assert ppkg.name==ppkgname
            p=pkgdir_for_search(ppkg,'libinc',p)
            if _ospath.exists(p) and _ospath.realpath(p)!=_ospath.realpath(f):
                res[_printform(ppkg,p,for_sortkey=True)] = (ppkg,p)
    _cache_incs_direct[f]=res
    return res

def _incs_recursive(pkg,f,out):
    for k,v in _incs_direct(pkg,f).items():
        if k in out:
            continue
        out[k]=v
        _incs_recursive(v[0],v[1],out)
    return out

_cache_incs_indirect={}
def _incs_indirect(pkg,f):
    global _cache_incs_indirect
    if f in _cache_incs_indirect:
        return _cache_incs_indirect[f]
    out={}
    _incs_recursive(pkg,f,out)
    for k,v in _incs_direct(pkg,f).items():
        del out[k]
    _cache_incs_indirect[f]=out
    return out

def collect_info(pkgloader,f):
    #collects info from single file and returns in dict.
    pkgname,subdir,fn = f.split(_ospath.sep)[-3:]
    pkg = pkgloader.name2pkg.get(pkgname,None)
    if not pkg or not f.startswith(pkg.dirname):
        utils.err('File %s not located inside a package'%f)
    #find isheader,lang from extension:
    _,ext = _ospath.splitext(f)
    isheader=True
    lang = langs.hdrext2lang.get(ext,None)
    if lang is None:
        isheader=False
        langs.srcext2lang.get(ext,None)

    lang = langs.srcext2lang.get(ext,langs.hdrext2lang.get(ext,None))
    if lang not in ['cxx','c']:
        utils.err('File %s not a C++ or C file'%f)

    nfo = dict(signature=(pkgname,subdir,fn),
               pkg=pkg,
               lang=lang,
               isheader=isheader,
               includes_indirectly=[],is_included_by_indirectly=[],
               includes_directly=[],is_included_by_directly=[])
    for _,(pi,fi) in sorted([(k,v) for k,v in _incs_direct(pkg,f).items()]):
        nfo['includes_directly'] += [(pi,fi)]
    for _,(pi,fi) in sorted([(k,v) for k,v in _incs_indirect(pkg,f).items()]):
        nfo['includes_indirectly'] += [(pi,fi)]
    #Now the harder part, include statements TO the file in question:
    if not isheader:
        return nfo
    #This is a header file, so in other words in can be included by other
    #files. First get the list of files which could possibly include the file in question.
    if subdir!='libinc':
        #only consider files in the same directory
        files = [(pkg,ff) for ff in ccxx_files_in_dir(pkgdir_for_search(pkg,subdir))]
    else:
        #the hardest task: consider files in all dependent packages
        files=[]
        pkgs=set(pkg.all_clients())
        pkgs.add(pkg)
        for pp in pkgs:
            for d in os.listdir(pkgdir_for_search(pp)):
                d=pkgdir_for_search(pp,d)
                if _ospath.isdir(d):
                    files += [(pp,ff) for ff in ccxx_files_in_dir(d)]
    files.remove((pkg,f))#not ourself
    files = [(_printform(pp,ff,for_sortkey=True),pp,ff) for pp,ff in files]
    files.sort()

    #ok, now we have a list of files which COULD include us, let us see who does:
    searchkey = _printform(pkg,f,for_sortkey=True)
    for _,pp,ff in files:
        if searchkey in _incs_direct(pp,ff):
            nfo['is_included_by_directly'] += [(pp,ff)]
    for _,pp,ff in files:
        if searchkey in _incs_indirect(pp,ff):
            nfo['is_included_by_indirectly'] += [(pp,ff)]
    return nfo

def _classify(nfo):
    return '%s %s'%({'cxx':'C++','c':'C'}[nfo['lang']],
                    "header" if nfo['isheader'] else "source")

def provide_info(pkgloader,f):
    from .io import print
    nfo = collect_info(pkgloader,f)
    print()
    print("Investigating %s file: %s"%(_classify(nfo),_printform(nfo['pkg'],f)))
    nrelationships = 0
    for i in ('includes','is included by'):
        for d in ('directly','indirectly'):
            l=['%s%s'%(_printform(pi,fi),_rel_description(f,fi)) for (pi,fi) in sorted(nfo['%s_%s'%(i.replace(' ','_'),d)])]
            if l:
                nrelationships += len(l)
                t='1 file' if len(l)==1 else '%i files'%len(l)
                print()
                print("File %s %s (%s):"%(i,t,d))
                print()
                for e in l:
                    print('      %s'%e)
    if not nrelationships:
        print()
        print("File neither includes nor is included by any other file in the framework")
    print()

def provide_info_multifiles(pkgloader,files):
    from .io import print
    nfos = dict((fn,collect_info(pkgloader,fn)) for fn in files)
    print()
    print("Investigating %i files:"%len(files))
    print()
    for fn in files:
        nfo = nfos[fn]
        print('      %s (%s)'%(_printform(nfo['pkg'],fn),_classify(nfo)))
    #find merged includes:
    merged_nfo = {}
    files_set = set(files)#ignore dependencies within the queried list of files
    for key in ('includes_directly', 'includes_indirectly', 'is_included_by_directly', 'is_included_by_indirectly'):
        seen,l=set(),[]
        for nfo in nfos.values():
            l += [v for v in nfo[key] if v[1] not in files_set and not (v in seen or seen.add(v))]#relies on seen.add returning None
        merged_nfo[key] = l
    #print results
    nrelationships = 0
    for i in ('includes','is included by'):
        for d in ('directly','indirectly'):
            l=[_printform(pi,fi) for (pi,fi) in sorted(merged_nfo['%s_%s'%(i.replace(' ','_'),d)])]
            if l:
                i_plural = {'includes':'include','is included by':'are included by'}[i]
                nrelationships += len(l)
                t='1 file' if len(l)==1 else '%i files'%len(l)
                print()
                print("Files %s %s (%s):"%(i_plural,t,d))
                print()
                for e in l:
                    print('      %s'%e)
    if not nrelationships:
        print()
        print("Files neither includes nor are included by other files in the framework")
    print()
