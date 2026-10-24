# Tests of build timings (sb --buildtimes).

import os
import platform
import re
import time
import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

def _sleep_before_modifying_sources():
    #On macOS, make only considers modification times with a resolution of
    #one second, so a source file modified shortly after it was compiled
    #would not be recompiled:
    time.sleep( 1.1 if platform.system() == 'Darwin' else 0.05 )

def _rows( out ):
    """Parse the table of sb --buildtimes into a list of (seconds,step)."""
    res = []
    for line in out.splitlines():
        m = re.match( r'^sbld:\s+([0-9.]+) \|\s+[0-9.]+%\s+\| (.*)$', line )
        if m:
            res.append( ( float(m.group(1)), m.group(2).strip() ) )
    return res

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'PkgA/pkg.info' : 'package()\n',
        'PkgA/libinc/A.hh' : 'int a_value();\n',
        'PkgA/libsrc/A.cc' : '#include "PkgA/A.hh"\nint a_value() { return 17; }\n',
        'PkgA/app_hello/main.cc' : ( '#include "PkgA/A.hh"\n'
                                     'int main() { return a_value() == 17 ? 0 : 1; }\n' ),
    } )
    return d

def test_buildtimes( proj ):
    d = proj
    res = run( 'sb --buildtimes', d )
    assert 'No build timings are available' in res.out
    run( 'sb', d )
    res = run( 'sb --buildtimes', d )
    rows = _rows( res.out )
    steps = [ s for _, s in rows ]
    for s in ( 'PkgA/libsrc/A.o', 'PkgA/app_hello/main.o',
               'PkgA/libsrc (linking)', 'PkgA/app_hello (linking)' ):
        assert s in steps
    #Slowest steps at the bottom:
    assert [ t for t, _ in rows ] == sorted( t for t, _ in rows )
    assert all( t >= 0.0 for t, _ in rows )
    assert 'Slowest packages:' in res.out and 'Total time of all steps:' in res.out
    #Only the slowest N steps:
    res = run( 'sb --buildtimes=2', d )
    assert _rows( res.out ) == rows[-2:]
    assert 'Build times of the 2 slowest of' in res.out
    #Timings are updated when files are rebuilt:
    marker = ( d / 'simplebuild_cache' / 'bld' / 'pc' / 'PkgA' / 'objs'
               / 'libsrc' / 'A.o.tstart' )
    t_before = marker.stat().st_mtime
    _sleep_before_modifying_sources()
    src = d / 'PkgA' / 'libsrc' / 'A.cc'
    src.write_text( src.read_text() + '//changed\n' )
    run( 'sb', d )
    assert marker.stat().st_mtime > t_before
    assert 'PkgA/libsrc/A.o' in [ s for _, s in _rows( run( 'sb --buildtimes', d ).out ) ]
    #A failed compilation is not listed (rather than with a wrong time):
    _sleep_before_modifying_sources()
    src.write_text( 'this does not compile\n' )
    run( 'sb', d, expect_ec = None )
    steps = [ s for _, s in _rows( run( 'sb --buildtimes', d ).out ) ]
    assert 'PkgA/libsrc/A.o' not in steps and 'PkgA/app_hello/main.o' in steps

def test_buildtimes_invalid_usage( proj ):
    res = run( 'sb --buildtimes=0', proj, expect_ec = 2 )
    assert '--buildtimes requires a positive number' in res.out
    res = run( 'sb -t --buildtimes', proj, expect_ec = 2 )
    assert 'not allowed with argument' in res.out or 'mutually exclusive' in res.out

def test_buildtimes_ignores_incomplete_steps( tmp_path ):
    #Unit-like test of the collection of timings from marker files:
    from _simple_build_system.buildtimes import collect_build_steps
    objs = tmp_path / 'pc' / 'PkgX' / 'objs'
    ( objs / 'libsrc' ).mkdir( parents = True )
    ( tmp_path / 'named_targets' / 'PkgX' ).mkdir( parents = True )
    def touch( p, t ):
        p.touch()
        os.utime( p, ( t, t ) )
    now = time.time()
    touch( objs / 'libsrc' / 'good.o.tstart', now - 10 )
    touch( objs / 'libsrc' / 'good.o', now - 7 )
    touch( objs / 'libsrc' / 'failed.o', now - 20 )
    touch( objs / 'libsrc' / 'failed.o.tstart', now - 5 )
    touch( objs / 'libsrc' / 'missing.o.tstart', now - 5 )
    touch( objs / 'libsrc.link.tstart', now - 4 )
    touch( tmp_path / 'named_targets' / 'PkgX' / 'libsrc', now - 3 )
    steps = sorted( ( s.label, round( s.seconds, 3 ) ) for s in collect_build_steps( tmp_path ) )
    assert steps == [ ( 'PkgX/libsrc (linking)', 1.0 ), ( 'PkgX/libsrc/good.o', 3.0 ) ]

def _have_numpy():
    try:
        import numpy # noqa F401
        return True
    except ImportError:
        return False

def test_includecosts_estimates():
    #Estimates from synthetic data: Shared.hh costs 3s and is used by all
    #translation units, Heavy.hh costs 5s and is used by two of them, and
    #each source file costs 0.1s:
    from sbtestutils import require_feature
    require_feature( 'numpy', _have_numpy() )
    from _simple_build_system.includecosts import estimate_costs
    tus = []
    for i in range(6):
        files = { f'src{i}.cc', 'Shared.hh' }
        t = 0.1 + 3.0
        if i < 2:
            files.add( 'Heavy.hh' )
            t += 5.0
        tus.append( ( t, files ) )
    costs = dict( ( tuple(c.labels), c ) for c in estimate_costs( tus ) )
    assert abs( costs[('Shared.hh',)].cost_per_use - 3.0 ) < 0.3
    assert costs[('Shared.hh',)].nuses == 6
    assert abs( costs[('Heavy.hh',)].cost_per_use - 5.0 ) < 0.5
    assert all( c.cost_per_use < 0.5 for k, c in costs.items()
                if k[0].startswith('src') )
    #Files used by the same translation units are grouped:
    tus2 = [ ( t, files | { 'Other.hh' } if 'Heavy.hh' in files else files )
             for t, files in tus ]
    labels = [ c.labels for c in estimate_costs( tus2 ) ]
    assert [ 'Heavy.hh', 'Other.hh' ] in labels

def test_includecosts( tmp_path ):
    #A header including the expensive <regex> header is used by three
    #translation units, and must be identified as the most costly:
    from sbtestutils import require_feature
    require_feature( 'numpy', _have_numpy() )
    d = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
              'PkgA/pkg.info' : 'package()\n',
              'PkgA/libinc/Heavy.hh' : ( '#include <regex>\n#include <string>\n'
                                         'inline bool heavy_match( const std::string& s )\n'
                                         '{ return std::regex_match( s, std::regex("a+b*") ); }\n' ),
              'PkgA/libinc/Light.hh' : 'inline int light_value() { return 1; }\n' }
    for i in range(3):
        files[f'PkgA/libsrc/heavy{i}.cc'] = ( '#include "PkgA/Heavy.hh"\n'
                                              f'bool fheavy{i}() {{ return heavy_match("aab"); }}\n' )
        files[f'PkgA/libsrc/light{i}.cc'] = ( '#include "PkgA/Light.hh"\n'
                                              f'int flight{i}() {{ return light_value(); }}\n' )
    write_files( d, files )
    run( 'sb', d )
    def rows( n ):
        res = run( f'sb --includecosts={n}', d )
        assert 'These are rough estimates' in res.out
        return [ line for line in res.out.splitlines()
                 if re.match( r'^sbld:\s+[0-9.]+ \|', line ) ]
    assert 0 < len( rows(2) ) <= 2
    #(NB: Files from the Core package, which is always built, might be even
    #more costly, so only consider files from PkgA):
    pkga = [ r for r in rows(100) if 'PkgA' in r ]
    assert 'PkgA/libinc/Heavy.hh' in pkga[-1] and '<regex>' in pkga[-1]
    assert re.search( r'\|\s+3 \| ', pkga[-1] )
