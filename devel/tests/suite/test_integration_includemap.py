# Tests of includes mapped by extdep include maps (ExtDep_<name>_INCLUDEMAPFILE)
# to package headers: such includes must be to headers of the package itself
# or of its dependencies (otherwise they would not be dependency-tracked),
# unless marked with "// sbld::nodep".

import platform
import time
import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

def _sleep_before_modifying_sources():
    #On macOS, make only considers modification times with a resolution of
    #one second:
    time.sleep( 1.1 if platform.system() == 'Darwin' else 0.05 )

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    ext = tmp_path / 'ext' / 'include'
    write_files( d, {
        'simplebuild.cfg' : ( '[bundle]\n  name = "proj"\n  pkg_root = "./pkgs"\n'
                              '  extdep_root = "./extdeps"\n' ),
        'extdeps/ExtDep_MyHeaders.cmake' : (
            'set( HAS_MyHeaders "1" )\n'
            'set( ExtDep_MyHeaders_VERSION "1.0" )\n'
            f'set( ExtDep_MyHeaders_COMPILE_FLAGS "-I{ext}" )\n'
            'set( ExtDep_MyHeaders_LINK_FLAGS "" )\n'
            'set( ExtDep_MyHeaders_IsNotSystemHeaders "ON" )\n'
            'set( ExtDep_MyHeaders_INCLUDEMAPFILE "${CMAKE_CURRENT_LIST_DIR}/incmap.txt" )\n' ),
        'extdeps/incmap.txt' : ( 'myproject/bar.hh PkgB/bar.hh\n'
                                 'myproject/gone.hh PkgB/gone.hh\n' ),
        'pkgs/PkgB/pkg.info' : 'package(USEEXT MyHeaders)\n',
        'pkgs/PkgA/pkg.info' : 'package(USEEXT MyHeaders)\n',
        'pkgs/PkgA/app_foo/main.cc' : ( '#include "myproject/bar.hh"\n'
                                        'int main() { return bar() == 1 ? 0 : 1; }\n' ),
    } )
    write_files( ext, { 'myproject/bar.hh' : 'inline int bar() { return 1; }\n',
                        'myproject/gone.hh' : 'inline int gone() { return 0; }\n' } )
    ( d / 'pkgs/PkgB/libinc' ).mkdir()
    ( d / 'pkgs/PkgB/libinc/bar.hh' ).symlink_to( ext / 'myproject' / 'bar.hh' )
    return d, ext

def test_mapped_include_requires_dependency( proj ):
    d, ext = proj
    res = run( 'sb', d, expect_ec = 1 )
    for e in ( 'PkgA/app_foo/main.cc includes "myproject/bar.hh"',
               'extdep MyHeaders translates to "PkgB/bar.hh"',
               'PkgA does not depend on a package named PkgB',
               'Add PkgB to the USEPKG list in PkgA/pkg.info',
               '"// sbld::nodep"' ):
        assert e in ' '.join( res.out.split() )
    #With the dependency, the header is tracked (changes trigger rebuilds):
    ( d / 'pkgs/PkgA/pkg.info' ).write_text( 'package(USEPKG PkgB USEEXT MyHeaders)\n' )
    run( 'sb -t', d )
    run( 'sbenv sb_pkga_foo', d )
    _sleep_before_modifying_sources()
    ( ext / 'myproject/bar.hh' ).write_text( 'inline int bar() { return 2; }\n' )
    res = run( 'sb', d )
    assert 'Building PkgA/app_foo' in res.out
    run( 'sbenv sb_pkga_foo', d, expect_ec = 1 )

def test_nodep_marker( proj ):
    d, _ = proj
    ( d / 'pkgs/PkgA/app_foo/main.cc' ).write_text(
        '#include "myproject/bar.hh" // sbld::nodep\n'
        'int main() { return bar() == 1 ? 0 : 1; }\n' )
    run( 'sb', d )
    run( 'sbenv sb_pkga_foo', d )

def test_mapped_include_in_header( proj ):
    #The check concerns the package of the file containing the include, also
    #for headers:
    d, _ = proj
    write_files( d, {
        'pkgs/PkgC/pkg.info' : 'package(USEEXT MyHeaders)\n',
        'pkgs/PkgC/libinc/baz.hh' : ( '#include "myproject/bar.hh"\n'
                                      'inline int baz() { return bar(); }\n' ),
        'pkgs/PkgA/pkg.info' : 'package(USEPKG PkgC USEEXT MyHeaders)\n',
        'pkgs/PkgA/app_foo/main.cc' : ( '#include "PkgC/baz.hh"\n'
                                        'int main() { return baz() == 1 ? 0 : 1; }\n' ),
    } )
    res = run( 'sb', d, expect_ec = 1 )
    out = ' '.join( res.out.split() )
    assert 'PkgC/libinc/baz.hh includes "myproject/bar.hh"' in out
    assert 'PkgC does not depend on a package named PkgB' in out
    ( d / 'pkgs/PkgC/pkg.info' ).write_text( 'package(USEPKG PkgB USEEXT MyHeaders)\n' )
    run( 'sb', d )
    run( 'sbenv sb_pkga_foo', d )

def test_mapped_include_to_missing_header( proj ):
    d, _ = proj
    write_files( d, {
        'pkgs/PkgA/pkg.info' : 'package(USEPKG PkgB USEEXT MyHeaders)\n',
        'pkgs/PkgA/app_foo/main.cc' : ( '#include "myproject/gone.hh"\n'
                                        'int main() { return gone(); }\n' ),
    } )
    res = run( 'sb', d, expect_ec = 1 )
    out = ' '.join( res.out.split() )
    assert 'translates to "PkgB/gone.hh", but package PkgB has no header file named "gone.hh"' in out
    assert 'Fix the include map, or remove the include' in out
