def decode_pattern(p):
    #pattern like '<delim><pat1><delim><pat2><delim>' (example "/bla/lala/" or "#bla#lala#"
    if len(p)<4 or p.count(p[0])!=3 or p[-1]!=p[0]:
        return None,None#error
    else:
        p=p.split(p[0])
        if len(p)!=4 or p[0] or p[-1]:
            return None,None#error
    return p[1],p[2]#search_pattern,replace_pattern

def replacefile(filename,printname,search_pattern,replace_pattern):
    import os
    import pathlib
    #Operate on the actual file (and not replace symlinks with files):
    path = pathlib.Path(os.path.realpath(filename))
    try:
        #NB: newline='' to keep line endings unchanged:
        with path.open('rt',encoding='utf-8',newline='') as fh:
            cont = fh.read()
    except UnicodeDecodeError:
        return 0#ignore non-text data files
    n = cont.count(search_pattern)
    if n:
        #at least one replacement made. Write atomically (to never leave behind
        #partially written source files), keeping the file permissions:
        from .utils import write_atomic
        data = cont.replace(search_pattern,replace_pattern).encode('utf-8')
        write_atomic( path, data, mode = path.stat().st_mode & 0o7777 )
        from .io import print
        print('  %50s : %i replacements'%(printname,n))
    return n

def replace(pkg,search_pattern,replace_pattern,filenames):
    from .grep import pkgfiles
    import os
    import pathlib
    pjoin=os.path.join
    n=0
    for f in pkgfiles(pkg):
        if filenames and pathlib.Path(f) not in filenames:
            continue
        n+=replacefile(pjoin(pkg.dirname,f),pjoin(pkg.name,f),search_pattern,replace_pattern)
    return n
