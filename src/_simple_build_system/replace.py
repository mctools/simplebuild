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
    n=0
    fh=open(filename,'rt')
    cont=''
    try:
        for l in fh:
            if search_pattern in l:
                n+=l.count(search_pattern)
                l=l.replace(search_pattern,replace_pattern)
            cont+=l
    except UnicodeDecodeError:
        #ignore non-text data files
        n=0
    fh.close()
    if n:
        #at least one replacement made
        fh=open(filename,'wt')
        fh.write(cont)
        fh.close()
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
