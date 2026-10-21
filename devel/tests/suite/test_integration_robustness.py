# Robustness of the build against broken or missing state in the cache
# directory, interrupted builds, and changes to packages. Previously, many of
# these situations required "sb -i" or "sb --removelock" to recover from.

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

_files = {
    'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
    'PkgA/pkg.info' : 'package()\n',
    'PkgA/libinc/A.hh' : 'int a_value();\n',
    'PkgA/libsrc/A.cc' : '#include "PkgA/A.hh"\nint a_value() { return 17; }\n',
    'PkgB/pkg.info' : 'package(USEPKG PkgA)\n',
    'PkgB/app_hello/main.cc' : ( '#include "PkgA/A.hh"\n#include <cstdio>\n'
                                 'int main() { std::printf("hello %i\\n",a_value()); return 0; }\n' ),
    'PkgB/pycpp_cmod/mod.cc' : ( '#include "Core/Python.hh"\n#include "PkgA/A.hh"\n'
                                 'PYTHON_MODULE( mod ) { mod.def("value",&a_value); }\n' ),
    'PkgB/python/pymod.py' : 'def value():\n    return 42\n',
    'PkgB/scripts/testpy' : ( '#!/usr/bin/env python3\nimport PkgB.cmod\nimport PkgB.pymod\n'
                              'print(PkgB.cmod.value(),PkgB.pymod.value())\n' ),
    'PkgB/scripts/testpy.log' : '17 42\n',
    'PkgB/data/somefile.txt' : 'somedata\n',
}

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, _files )
    ( d / 'PkgB' / 'scripts' / 'testpy' ).chmod( 0o755 )
    res = run( 'sb -t', d )
    assert 'All tests completed without failures!' in res.out
    return d

def bld( d ):
    return d / 'simplebuild_cache' / 'bld'

def inst( d ):
    return d / 'simplebuild_cache' / 'install'

def check_ok( d ):
    res = run( 'sb -t', d )
    assert 'All tests completed without failures!' in res.out
    assert run( 'sbenv sb_pkgb_hello', d ).stdout.strip() == 'hello 17'
    return res

@pytest.mark.parametrize( 'relpath', [ 'globdb.pkl', 'env.cache',
                                       'systimestamp.cache' ] )
@pytest.mark.parametrize( 'damage', [ 'garbage', 'truncate', 'remove' ] )
def test_broken_global_state( proj, relpath, damage ):
    f = bld( proj ) / relpath
    assert f.is_file()
    if damage == 'remove':
        f.unlink()
    elif damage == 'truncate':
        f.write_bytes( f.read_bytes()[:20] )
    else:
        f.write_bytes( b'garbage' )
    check_ok( proj )

def test_broken_pkg_state( proj ):
    #Make PkgB load its targets from pickle (by changing PkgA), but break the
    #pickle file first:
    ( bld( proj ) / 'pc' / 'PkgB' / 'targets.pkl' ).write_bytes( b'garbage' )
    ( proj / 'PkgA' / 'libsrc' / 'A.cc' ).write_text(
        '#include "PkgA/A.hh"\nint a_value() { return 18; }\n' )
    ( proj / 'PkgB' / 'scripts' / 'testpy.log' ).write_text( '18 42\n' )
    res = run( 'sb -t', proj )
    assert 'All tests completed without failures!' in res.out
    assert run( 'sbenv sb_pkgb_hello', proj ).stdout.strip() == 'hello 18'

def test_missing_makefile( proj ):
    ( bld( proj ) / 'makefiles' / 'Makefile_PkgB.make' ).unlink()
    check_ok( proj )

def test_killed_during_build( proj ):
    #Kill sb (SIGKILL, so no cleanup is possible) in the middle of a build. The
    #next invocation must recover automatically (incl. removal of the stale
    #lock):
    import signal
    import subprocess
    import time
    from sbtestutils import clean_env
    for f in ( 'PkgA/libsrc/A.cc', 'PkgB/app_hello/main.cc',
               'PkgB/pycpp_cmod/mod.cc' ):
        p = proj / f
        p.write_text( p.read_text() + '\n//changed\n' )
    p = subprocess.Popen( [ 'sb', '-j1' ], cwd = proj, env = clean_env(),
                          stdout = subprocess.PIPE, stderr = subprocess.STDOUT )
    t0 = time.time()
    for line in p.stdout:
        if b'Building' in line:
            break
        assert time.time() - t0 < 300
    p.send_signal( signal.SIGKILL )
    p.wait()
    p.stdout.close()
    time.sleep( 0.5 )#let orphaned compilations finish
    assert ( bld( proj ) / '.lock' ).exists()
    res = check_ok( proj )
    assert 'Removing stale lock file' in res.out
