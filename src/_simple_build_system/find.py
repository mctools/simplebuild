def find( pkg, matcher, filenames = None ):
    #Find package files and directories (the package directory itself and its
    #subdirectories) with paths matched by the matcher (see querypattern.py).
    import os
    import pathlib
    from .grep import pkgfiles, pkgsubdirs, is_selected
    from . import col
    from .io import print

    pkgcol = col.ok if pkg.enabled else col.bad

    n=0
    pkg_rd = pkg.reldirname#always match on package reldir
    cwd = pathlib.Path.cwd()

    def show( flocal, isdir ):
        print( '   %s%s%s%s'%( pkgcol,
                               os.path.relpath((pkg.dirname / flocal),cwd),
                               '/' if isdir else '',
                               col.end ) )

    for d in [ pathlib.Path('.') ] + [ pathlib.Path(e) for e in pkgsubdirs(pkg) ]:
        if is_selected( d, filenames ) and matcher.search( str( pkg_rd / d ) ):
            show( d, isdir = True )
            n+=1

    for flocal in pkgfiles(pkg):
        flocal = pathlib.Path(flocal)
        if not is_selected( flocal, filenames ):
            continue
        if matcher.search( str(pkg_rd / flocal) ):
            show( flocal, isdir = False )
            n+=1

    return n
