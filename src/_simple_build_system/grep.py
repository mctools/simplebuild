import os
pjoin=os.path.join

def grepfile(filename,pattern,color=None):
    from . import col
    fh=None
    if filename.endswith('.gz'):
        import gzip
        try:
            fh=gzip.open(filename,'rt')
            #read a bit, to trigger error here (in case file with extension .gz
            #is not actually compressed with gzip)
            try:
                for ll in fh:
                    break
            except UnicodeDecodeError:
                return#ignore gzipped non-text data files
            fh.seek(0)#rewind
        except (IOError,OSError):
            fh=None
    if fh is None:
        fh=open(filename)
    lp=pattern.lower()
    try:
        for i,lorig in enumerate(fh):
            ll=lorig.lower()
            if lp.lower() in ll:
                if color is None:
                    yield (i+1,lorig)
                else:
                    used=0
                    l2=''
                    while used<len(ll):
                        k=ll[used:].find(lp)
                        if k==-1:
                            l2+=lorig[used:]
                            break
                        else:
                            l2+=lorig[used:used+k]
                            l2+=color
                            l2+=lorig[used+k:used+k+len(lp)]
                            l2+=col.grep_unmatch
                            used+=k+len(pattern)
                    yield (i+1,col.grep_unmatch+l2+col.end)
    except UnicodeDecodeError:
        pass#ignore non-text data files
    fh.close()

#TODO to dirs.py ?:
def pkgdir_for_search(pkg,*subpath):
    return os.path.join(pkg.dirname,*subpath)

def pkgfiles(pkg):
    #Attempt to return files which are meaningful (to keep it simple, we say it
    #is all files in subdirs + the pkg.info file).
    from . import conf
    d = pkgdir_for_search(pkg)
    yield conf.package_cfg_file
    for d2rel in os.listdir(d):
        d2=pjoin(d,d2rel)
        if os.path.isdir(d2):
            for frel in os.listdir(d2):
                if not conf.ignore_file(frel):
                    if not os.path.isdir(pjoin(d2,frel)):
                        yield pjoin(d2rel,frel)

def grep(pkg,pattern,filenames=None,countonly=False):
    import pathlib
    from . import col
    n=0
    from .io import print
    col_match = None if countonly else col.grep_match
    for f in pkgfiles(pkg):
        f = pathlib.Path(f)
        if filenames and f not in filenames:
            continue
        pdir=pkgdir_for_search(pkg)
        ff=pjoin(pdir,f)
        for linenum,line in grepfile( ff, pattern, color = col_match):
            n+=1
            if countonly:
                continue
            pkgdir=os.path.relpath(pdir)
            pkgdir=(col.ok if pkg.enabled else col.bad) + pkgdir + col.end
            output = '  %s/%s [L%i]: %s'%(pkgdir,f,linenum,line)
            if '\n' not in output:
                output += '\n'
            print(output,end='')
    if countonly and n:
        pn=pkg.name
        pn=(col.ok if pkg.enabled else col.bad) + pn + col.end
        print('%s : %i hits'%(pn.rjust(30),n))
    return n
