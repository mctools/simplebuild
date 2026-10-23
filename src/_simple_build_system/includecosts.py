# Rough estimates of the compilation cost of individual files ("sb
# --includecosts"), based on the build timings (see buildtimes.py) and the
# include statements in the code.
#
# Each translation unit (object file) is considered to need a set of files: its
# source file, all project header files which it includes directly or
# indirectly, and the system headers (#include <...>) included by any of
# those. Its compilation time is modelled as the sum of the costs of those
# files. Since a source file belongs to a single translation unit, there are
# more unknowns than measurements, so the fit is regularised (all costs are
# non-negative): costs of files needed by a single translation unit (like its
# source file) are penalised much more than costs of shared files. Thus, costs
# common to the translation units sharing a file are attributed to that file,
# and only the remainder is attributed to the source files. Files needed by
# exactly the same translation units can not be distinguished, and are treated
# as a group. The costs of files included by system headers are attributed to
# the system headers.
#
# This is a rough estimate (the cost of a header depends on the context in which
# it is included, and timings from parallel builds are noisy), meant to find
# the worst offenders. It requires numpy.

import os
import re

_sysinc = re.compile( rb'^\s*#\s*include\s*<\s*([^>\s]+)\s*>' ).match

def _system_includes( path ):
    from .utils import include_candidate_lines
    res = set()
    try:
        lines = include_candidate_lines( path )
    except RuntimeError:
        return res
    for line in lines:
        m = _sysinc( line )
        if m:
            res.add( '<%s>'%m.group(1).decode( 'utf8', errors = 'replace' ) )
    return res

def _label( path ):
    return '/'.join( os.path.normpath( path ).split( os.sep )[-3:] )

def _find_source( pkg, subdir, objname ):
    from . import langs
    stem = os.path.splitext( objname )[0]
    for ext, lang in sorted( langs.srcext2lang.items() ):
        if lang in ( 'c', 'cxx' ):
            f = os.path.join( pkg.dirname, subdir, stem + ext )
            if os.path.isfile( f ):
                return f
    return None

def collect_translation_units( pkgloader, blddir ):
    """Returns list of (seconds,set_of_file_labels) for all compiled objects
    with timings."""
    from .buildtimes import collect_build_steps
    from .incinfo import _incs_recursive
    sysinc_cache = {}
    def sysincs( f ):
        if f not in sysinc_cache:
            sysinc_cache[f] = _system_includes( f )
        return sysinc_cache[f]
    tus = []
    for step in collect_build_steps( blddir ):
        if step.objname is None:
            continue#linking
        pkg = pkgloader.name2pkg.get( step.pkgname )
        if not pkg or not pkg.enabled:
            continue
        src = _find_source( pkg, step.subdir, step.objname )
        if not src:
            continue
        files = [ src ] + [ f for _, f in _incs_recursive( pkg, src, {} ).values() ]
        labels = set( _label(f) for f in files )
        for f in files:
            labels.update( sysincs(f) )
        tus.append( ( step.seconds, labels ) )
    return tus

def nnls( A, b ):
    """Non-negative least squares (Lawson-Hanson active set method): minimise
    |Ax-b| subject to x>=0. This implementation works with the normal
    equations, which is fast, but only appropriate when A^T*A is well
    conditioned (as is the case here due to the regularisation)."""
    import numpy as np
    m, n = A.shape
    AtA = A.T @ A
    Atb = A.T @ b
    x = np.zeros( n )
    passive = np.zeros( n, dtype = bool )
    tol = 10 * np.finfo(float).eps * np.linalg.norm( A, 1 ) * max( m, n )
    def solve_passive():
        z = np.zeros( n )
        idx = np.flatnonzero( passive )
        z[idx] = np.linalg.solve( AtA[np.ix_(idx,idx)], Atb[idx] )
        return z
    w = Atb - AtA @ x
    for _ in range( 3 * n + 10 ):
        candidates = ( ~passive ) & ( w > tol )
        if not candidates.any():
            break
        passive[ np.argmax( np.where( candidates, w, -np.inf ) ) ] = True
        while True:
            z = solve_passive()
            if ( z[passive] > tol ).all():
                break
            neg = passive & ( z <= tol )
            alpha = np.min( x[neg] / ( x[neg] - z[neg] ) )
            x = x + alpha * ( z - x )
            passive &= ( x > tol )
            x[~passive] = 0.0
        x = z
        w = Atb - AtA @ x
    return x

class FileCost:

    def __init__( self, labels, cost_per_use, nuses ):
        self.labels = labels#several if files can not be distinguished
        self.cost_per_use = cost_per_use
        self.nuses = nuses

    @property
    def total( self ):
        return self.cost_per_use * self.nuses

def estimate_costs( tus, reg_single = 1e-2, reg_shared = 1e-5 ):
    """Estimate costs of files from list of translation units (as returned by
    collect_translation_units). Returns list of FileCost objects."""
    import numpy as np
    #Group files used by exactly the same translation units:
    users = {}
    for i, ( _, labels ) in enumerate( tus ):
        for lbl in labels:
            users.setdefault( lbl, [] ).append( i )
    groups = {}
    for lbl, idx in users.items():
        groups.setdefault( tuple(idx), [] ).append( lbl )
    groups = sorted( ( sorted(lbls), idx ) for idx, lbls in groups.items() )
    A = np.zeros( ( len(tus), len(groups) ) )
    for j, ( _, idx ) in enumerate( groups ):
        A[list(idx),j] = 1.0
    b = np.array( [ t for t, _ in tus ] )
    #Regularisation (see above):
    n = len(groups)
    reg = np.array( [ ( reg_single if len(idx) == 1 else reg_shared )
                      for _, idx in groups ] )
    Aaug = np.vstack( [ A, np.diag( np.sqrt(reg) ) ] )
    baug = np.concatenate( [ b, np.zeros(n) ] )
    x = nnls( Aaug, baug )
    return [ FileCost( lbls, float(x[j]), len(idx) )
             for j, ( lbls, idx ) in enumerate( groups ) ]

def _fmt_labels( labels, maxshow = 3 ):
    s = ' + '.join( labels[:maxshow] )
    if len(labels) > maxshow:
        s += ' (+%i more)'%( len(labels) - maxshow )
    return s

def _import_numpy():
    #The matrices are small, so multithreaded linear algebra only adds overhead
    #(and can be very slow when the CPUs are busy). This only has an effect if
    #numpy was not imported already:
    for v in ( 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS' ):
        os.environ.setdefault( v, '1' )
    import numpy # noqa F401

def print_report( pkgloader, blddir, nshow ):
    from .io import print
    from . import error
    try:
        _import_numpy()
    except ImportError:
        error.error('The --includecosts option requires the Python module numpy'
                    ' (install with e.g. "conda install numpy" or "python3 -m'
                    ' pip install numpy").')
    tus = collect_translation_units( pkgloader, blddir )
    if not tus:
        print('No build timings are available (they are recorded when files are built).')
        print()
        return
    costs = [ c for c in estimate_costs( tus ) if c.total > 0.0 ]
    costs.sort( key = lambda c : ( c.total, c.labels ) )
    total_time = sum( t for t, _ in tus ) or 1e-9
    nshow = min( nshow, len(costs) )
    print( 'Estimated compilation costs of files (the %i most costly, based on the'
           ' timings of %i compiled files):'%( nshow, len(tus) ) )
    print()
    hr = '  ' + '-'*11 + '+' + '-'*9 + '+' + '-'*13 + '+' + '-'*7 + '+' + '-'*50
    print( hr )
    print( '  Total [s]  |  Share  | Per use [s] |  Uses | File(s)' )
    print( hr )
    #The most costly files at the bottom, where they remain visible:
    for c in costs[-nshow:]:
        print( '  %10.2f | %5.1f%%  | %11.3f | %5i | %s'%( c.total, 100.0 * c.total / total_time,
                                                         c.cost_per_use, c.nuses,
                                                         _fmt_labels( c.labels ) ) )
    print( hr )
    print()
    print( 'These are rough estimates, obtained by modelling the compilation time of'
           ' each file as the sum of the costs of the files it needs (its source'
           ' file, the header files of the project it includes directly or'
           ' indirectly, and the system headers included by those). Costs of'
           ' files included by system headers are attributed to those system'
           ' headers, and files always needed together can not be distinguished'
           ' (they are shown together).' )
    print()
