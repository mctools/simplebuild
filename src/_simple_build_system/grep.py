import os
pjoin=os.path.join

def grepfile(filename,matcher,color=None):
    #Yields (linenumber,line) for lines in which the matcher (see
    #querypattern.py) finds a match, with the matches highlighted if color is
    #given. Non-text files are ignored, and a warning is emitted for files which
    #can not be read.
    from . import col
    fh=None
    try:
        if filename.endswith('.gz'):
            import gzip
            try:
                fh=gzip.open(filename,'rt')
                #read a bit, to trigger error here (in case file with extension
                #.gz is not actually compressed with gzip)
                try:
                    for ll in fh:
                        break
                except UnicodeDecodeError:
                    fh.close()
                    return#ignore gzipped non-text data files
                fh.seek(0)#rewind
            except (IOError,OSError,EOFError):
                if fh is not None:
                    fh.close()
                fh=None
        if fh is None:
            fh=open(filename)
    except OSError as e:
        from . import error
        error.warn(f'Could not read {filename} ({e.strerror or e})')
        return
    try:
        for i,lorig in enumerate(fh):
            if not matcher.search(lorig):
                continue
            spans = ( [ m.span() for m in matcher.finditer(lorig) if m.end() > m.start() ]
                      if color is not None else None )
            if color is None or not spans:
                yield (i+1,lorig)
                continue
            l2=''
            used=0
            for a,b in spans:
                l2 += lorig[used:a] + color + lorig[a:b] + col.grep_unmatch
                used = b
            l2 += lorig[used:]
            yield (i+1,col.grep_unmatch+l2+col.end)
    except UnicodeDecodeError:
        pass#ignore non-text data files
    except OSError as e:
        from . import error
        error.warn(f'Could not read {filename} ({e.strerror or e})')
    finally:
        fh.close()

#TODO to dirs.py ?:
def pkgdir_for_search(pkg,*subpath):
    return os.path.join(pkg.dirname,*subpath)

def is_selected( relpath, filenames ):
    #Whether a path (relative to the package dir) is selected by filenames,
    #which is None (everything is selected), or a list of files or directories
    #(relative to the package dir) given on the command line.
    import pathlib
    relpath = pathlib.Path(relpath)
    return not filenames or any( ( relpath == fn or fn in relpath.parents )
                                 for fn in filenames )

def pkgsubdirs(pkg):
    #The (non-ignored) subdirectories of the package directory.
    from . import conf
    d = pkgdir_for_search(pkg)
    for d2rel in sorted(os.listdir(d)):
        if os.path.isdir(pjoin(d,d2rel)) and not conf.ignore_file(d2rel):
            yield d2rel

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

def grep(pkg,matcher,filenames=None,countonly=False):
    import pathlib
    from . import col
    n=0
    from .io import print
    col_match = None if countonly else col.grep_match
    for f in pkgfiles(pkg):
        f = pathlib.Path(f)
        if not is_selected( f, filenames ):
            continue
        pdir=pkgdir_for_search(pkg)
        ff=pjoin(pdir,f)
        for linenum,line in grepfile( ff, matcher, color = col_match):
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
        print('%s : %i hit%s'%(pn.rjust(30),n,'' if n==1 else 's'))
    return n
