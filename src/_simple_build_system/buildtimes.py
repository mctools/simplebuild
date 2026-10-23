# Build timings ("sb --buildtimes"). The makefile recipes record the start time
# of each compilation and linking step with a marker file (see
# tfact_binary.py), and the end time is the modification time of the object
# file (for compilation) or the named target (for linking). Thus, timings are
# available for the most recent build of each file, without any special
# builds being needed.

import pathlib

class BuildStep:

    def __init__( self, pkgname, label, seconds, subdir, objname = None ):
        self.pkgname = pkgname
        self.label = label
        self.seconds = seconds
        self.subdir = subdir
        self.objname = objname#None for linking steps

def _duration( start_marker, end_file ):
    try:
        t0 = start_marker.stat().st_mtime
        t1 = end_file.stat().st_mtime
    except OSError:
        return None
    #(If the end file is older than the marker, the step did not complete,
    #e.g. due to a compilation error):
    return t1 - t0 if t1 >= t0 else None

def collect_build_steps( blddir ):
    """Returns a list of BuildStep objects for all files built in the given
    build directory, for which timings are available."""
    blddir = pathlib.Path( blddir )
    steps = []
    pcdir = blddir / 'pc'
    if not pcdir.is_dir():
        return steps
    for pkgdir in sorted( pcdir.iterdir() ):
        objsdir = pkgdir / 'objs'
        if not objsdir.is_dir():
            continue
        pkgname = pkgdir.name
        for marker in sorted( objsdir.glob('*/*.o.tstart') ):
            obj = marker.with_name( marker.name[:-len('.tstart')] )
            dt = _duration( marker, obj )
            if dt is not None:
                steps.append( BuildStep( pkgname, '%s/%s/%s'%( pkgname, marker.parent.name,
                                                               obj.name ), dt,
                                         marker.parent.name, obj.name ) )
        for marker in sorted( objsdir.glob('*.link.tstart') ):
            subdir = marker.name[:-len('.link.tstart')]
            dt = _duration( marker, blddir / 'named_targets' / pkgname / subdir )
            if dt is not None:
                steps.append( BuildStep( pkgname, '%s/%s (linking)'%( pkgname, subdir ),
                                         dt, subdir ) )
    return steps

def _fmt( seconds ):
    if seconds < 60.0:
        return '%.1fs'%seconds
    from .testreportui import format_duration
    return format_duration( seconds )

def print_report( blddir, nshow ):
    from .io import print
    steps = collect_build_steps( blddir )
    if not steps:
        print('No build timings are available (they are recorded when files are built).')
        print()
        return
    steps.sort( key = lambda s : ( s.seconds, s.label ) )
    total = sum( s.seconds for s in steps ) or 1e-9
    nshow = min( nshow, len(steps) )
    print( 'Build times of the %s (from the most recent build of each file):'%(
        f'{len(steps)} compilation and linking steps' if nshow == len(steps)
        else f'{nshow} slowest of {len(steps)} compilation and linking steps' ) )
    print()
    hr = '  ' + '-'*11 + '+' + '-'*9 + '+' + '-'*60
    print( hr )
    print( '   Time [s]  |  Share  | Step' )
    print( hr )
    #The slowest steps at the bottom, where they remain visible:
    for s in steps[-nshow:]:
        print( '  %10.2f | %5.1f%%  | %s'%( s.seconds, 100.0 * s.seconds / total, s.label ) )
    print( hr )
    print()
    pkgtimes = {}
    for s in steps:
        pkgtimes[s.pkgname] = pkgtimes.get( s.pkgname, 0.0 ) + s.seconds
    slowest_pkgs = sorted( pkgtimes.items(), key = lambda e : ( -e[1], e[0] ) )[:5]
    print( 'Slowest packages: ' + ', '.join( '%s (%s)'%( n, _fmt(t) )
                                              for n, t in slowest_pkgs ) )
    print( 'Total time of all steps: %s (the actual time of a build is shorter when'
           ' several steps run in parallel, while timings might be inflated when'
           ' the parallel steps compete for resources).'%_fmt( total ) )
    print()
