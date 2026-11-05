# Tests of the package queries --pkginfo, --pkggraph, --activegraph, --incinfo
# and --includecosts, which do not perform the configuration step of a build
# (no cmake inspection of the environment, no makefiles, no lock).

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : ( '[bundle]\n  name = "proj"\n'
                              '  extdep_root = "./extdeps"\n' ),
        'extdeps/ExtDep_MyMissingDep.cmake' : 'set( HAS_MyMissingDep "0" )\n',
        'PkgA/pkg.info' : 'package()\n',
        'PkgA/libinc/A.hh' : 'inline int a() { return 1; }\n',
        'PkgB/pkg.info' : 'package(USEPKG PkgA)\n',
        'PkgB/libinc/B.hh' : '#include "PkgA/A.hh"\ninline int b() { return a(); }\n',
        'PkgC/pkg.info' : 'package(USEPKG PkgB USEEXT MyMissingDep)\n',
    } )
    return d

def _lines( out ):
    return [ e.replace( 'sbld:', '' ).strip() for e in out.splitlines() ]

def test_no_configuration( proj ):
    #Without an earlier build, nothing is configured (and the cache dir is not
    #created):
    d = proj
    res = run( 'sb --pkginfo PkgC', d )
    assert 'CMake' not in res.out
    lines = _lines( res.out )
    assert 'Enabled                 : Yes' in lines
    assert 'The presence of the external dependencies is not yet known.' in lines
    res = run( 'sb --incinfo PkgB/B.hh', d )
    assert 'PkgA/libinc/A.hh' in res.out
    assert not ( d / 'simplebuild_cache' ).exists()
    #The package graph is written in the build directory:
    res = run( 'sb --pkggraph', d, expect_ec = None )
    assert 'CMake' not in res.out
    assert ( d / 'simplebuild_cache' / 'bld' / 'pkggraph.dot' ).is_file()
    assert not ( d / 'simplebuild_cache' / 'bld' / 'env.cache' ).exists()

def test_after_build( proj ):
    #After a build, the results of the inspection of the environment are used:
    d = proj
    run( 'sb', d )
    res = run( 'sb --pkginfo PkgC', d )
    lines = _lines( res.out )
    assert 'Enabled                 : No' in lines
    assert 'not yet known' not in res.out
    #Queries do not trigger any rebuilds, even when the timestamps of the
    #system changed:
    ( d / 'simplebuild_cache' / 'bld' / 'systimestamp.cache' ).unlink()
    res = run( 'sb --pkginfo PkgA', d )
    assert 'rebuild' not in res.out
    #(the next build does):
    assert 'complete rebuild' in run( 'sb', d ).out
