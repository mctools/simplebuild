def find( pkg, pattern, filenames = None ):
    import os
    import fnmatch
    import pathlib
    from .grep import pkgfiles
    from . import col
    pkgcol = col.ok if pkg.enabled else col.bad

    n=0
    pkg_rd = pkg.reldirname#always match on package reldir
    pattern='*%s*'%pattern.lower()
    from .io import print
    cwd = pathlib.Path.cwd()
    for flocal in pkgfiles(pkg):
        flocal = pathlib.Path(flocal)
        if filenames and flocal not in filenames:
            continue
        if fnmatch.fnmatch( str(pkg_rd / flocal).lower(), pattern ):
            #os.path.relpath does not have pathlib equivalent here
            print( '   %s%s%s'%( pkgcol,
                                 os.path.relpath((pkg.dirname / flocal),cwd),
                                 col.end ) )
            n+=1

    return n
