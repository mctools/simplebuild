# Robustness of the build against broken or missing state in the cache
# directory, interrupted builds, and changes to packages. Previously, many of
# these situations required "sb -i" or "sb --removelock" to recover from.

import os

import pytest

from sbtestutils import clean_env, n_compiled, run, write_files

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

def test_broken_symlink_state( proj ):
    for f in ( bld( proj ) / 'pc' / 'PkgB' / 'symlinks' ).glob( '*.pkl*' ):
        f.write_bytes( b'garbage' )
    #Touch a file to trigger reconfiguration of the package:
    ( proj / 'PkgB' / 'data' / 'other.txt' ).write_text( 'x\n' )
    check_ok( proj )
    assert ( inst( proj ) / 'data' / 'PkgB' / 'other.txt' ).is_symlink()

def test_dangling_symlink_repaired( proj ):
    #An installed symlink pointing somewhere else (e.g. a file which was
    #moved) is repaired when the links of the package are updated:
    link = inst( proj ) / 'scripts' / 'sb_pkgb_testpy'
    link.unlink()
    link.symlink_to( proj / 'nonexisting' )
    write_files( proj, { 'PkgB/scripts/other' : '#!/usr/bin/env bash\necho hi\n' } )
    ( proj / 'PkgB' / 'scripts' / 'other' ).chmod( 0o755 )
    check_ok( proj )
    assert link.resolve() == ( proj / 'PkgB' / 'scripts' / 'testpy' ).resolve()

def test_removed_parts_are_uninstalled( proj ):
    import shutil
    app = inst( proj ) / 'bin' / 'sb_pkgb_hello'
    pydir = inst( proj ) / 'python' / 'PkgB'
    assert app.is_file()
    assert any( pydir.glob( 'cmod.*' ) )
    #Remove the app:
    shutil.rmtree( proj / 'PkgB' / 'app_hello' )
    run( 'sb', proj )
    assert not app.exists()
    #Remove the compiled module (but keep the pure python module):
    shutil.rmtree( proj / 'PkgB' / 'pycpp_cmod' )
    ( proj / 'PkgB' / 'scripts' / 'testpy' ).write_text(
        '#!/usr/bin/env python3\nimport PkgB.pymod\nprint(17,PkgB.pymod.value())\n' )
    run( 'sb', proj )
    assert not any( pydir.glob( 'cmod.*' ) )
    assert ( pydir / 'pymod.py' ).exists()
    res = run( [ 'sbenv', 'python3', '-c', 'import PkgB.cmod' ], proj,
               expect_ec = None )
    assert res.ec != 0 and 'No module named' in res.out
    #Remove scripts and data entirely:
    shutil.rmtree( proj / 'PkgB' / 'scripts' )
    shutil.rmtree( proj / 'PkgB' / 'data' )
    run( 'sb', proj )
    assert not any( ( inst( proj ) / 'scripts' ).glob( 'sb_pkgb_*' ) )
    assert not ( inst( proj ) / 'data' / 'PkgB' ).exists()

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

def test_test_results( tmp_path ):
    #Test timings must be reported, and tests killed before reporting their
    #exit code must be reported as failures (and not crash sb):
    import xml.etree.ElementTree as ET
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/testslow' : '#!/usr/bin/env bash\nsleep 1\n',
        'MyPkg/scripts/testkilled' : '#!/usr/bin/env bash\nkill -9 $PPID\n',
    } )
    for f in ( 'testslow', 'testkilled' ):
        ( d / 'MyPkg' / 'scripts' / f ).chmod( 0o755 )
    res = run( 'sb -t', d, expect_ec = 73 )
    assert 'Traceback' not in res.out
    lines = [ e for e in res.out.splitlines() if 'sb_mypkg_test' in e ]
    assert any( 'sb_mypkg_testkilled' in e and 'FAIL' in e for e in lines )
    assert any( 'sb_mypkg_testslow' in e and ' OK ' in e for e in lines )
    xmlfile = bld( d ) / 'testresults' / 'simplebuild_test_results_junitformat.xml'
    times = { tc.get('name') : float( tc.get('time') )
              for tc in ET.parse( xmlfile ).getroot().iter( 'testcase' ) }
    assert times['sb_mypkg_testslow'] >= 0.9
    #Test filters:
    res = run( "sb -t --testfilter='*slow'", d )
    assert 'sb_mypkg_testslow' in res.out and 'sb_mypkg_testkilled' not in res.out
    res = run( "sb -t --testfilter='!*killed'", d )
    assert 'sb_mypkg_testslow' in res.out and 'sb_mypkg_testkilled' not in res.out

def test_makefiles_use_same_python( proj ):
    #The generated makefiles must use the python interpreter running
    #simplebuild, and not whatever "python3" is in the PATH:
    import shlex
    import sys
    mf = ( bld( proj ) / 'makefiles' / 'Makefile' ).read_text()
    assert f'PYTHON := {shlex.quote(sys.executable)}\n' in mf
    pkgmf = ( bld( proj ) / 'makefiles' / 'Makefile_PkgB.make' ).read_text()
    assert '${PYTHON} -m_simple_build_system.instsl ' in pkgmf
    assert 'python3 -m' not in pkgmf

def test_reinspect_on_flag_env_changes( proj ):
    res = run( 'sb', proj, env_extra = { 'CXXFLAGS' : '-DSBTEST_DUMMY_FLAG=1' } )
    assert 'Change in environment detected' in res.out
    assert 'CXXFLAGS' in res.out
    res = run( 'sb', proj, env_extra = { 'CXXFLAGS' : '-DSBTEST_DUMMY_FLAG=1' } )
    assert 'Change in environment detected' not in res.out

@pytest.mark.parametrize( 'badchar', [ '$', ':', '#', '(', ' ' ] )
def test_unsafe_cachedir_path( tmp_path, badchar ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : ( '[bundle]\nname = "proj"\n[build]\n'
                              f'cachedir = "./cache{badchar}dir"\n' ),
        'MyPkg/pkg.info' : 'package()\n',
    } )
    res = run( 'sb', d, expect_ec = 1 )
    assert ( 'path contains unsupported characters' in res.out
             or 'Colons not allowed in cache dir' in res.out )
    assert 'Traceback' not in res.out

def test_replace( tmp_path ):
    import os
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/myscript' : '#!/usr/bin/env bash\necho FOOBAR\n',
        'MyPkg/data/crlf.txt' : 'FOOBAR\r\nline2\r\n',
        'elsewhere/real.txt' : 'FOOBAR here\n',
    } )
    script = d / 'MyPkg' / 'scripts' / 'myscript'
    script.chmod( 0o755 )
    link = d / 'MyPkg' / 'data' / 'link.txt'
    link.symlink_to( d / 'elsewhere' / 'real.txt' )
    res = run( 'sb --replace /FOOBAR/BAZ/', d )
    assert 'replacements' in res.out
    assert script.read_text() == '#!/usr/bin/env bash\necho BAZ\n'
    assert os.stat( script ).st_mode & 0o777 == 0o755
    assert ( d / 'MyPkg' / 'data' / 'crlf.txt' ).read_bytes() == b'BAZ\r\nline2\r\n'
    assert link.is_symlink()
    assert ( d / 'elsewhere' / 'real.txt' ).read_text() == 'BAZ here\n'

def test_pkgname_prefix_clash( tmp_path ):
    #Packages Foo and Foo_Bar have installed commands with clashing name
    #patterns (sb_foo_*). Removing parts of Foo, or Foo itself, must not
    #affect Foo_Bar:
    import shutil
    d = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n' }
    for pkg in ( 'Foo', 'Foo_Bar' ):
        files.update( {
            f'{pkg}/pkg.info' : 'package()\n',
            f'{pkg}/scripts/bar_hello' : f'#!/usr/bin/env bash\necho script {pkg}\n',
            f'{pkg}/scripts/bar_hello.log' : f'script {pkg}\n',
            f'{pkg}/app_bar_app/main.cc' : ( '#include <cstdio>\nint main()'
                                             f' {{ std::printf("app {pkg}\\n"); return 0; }}\n' ),
        } )
    write_files( d, files )
    for pkg in ( 'Foo', 'Foo_Bar' ):
        ( d / pkg / 'scripts' / 'bar_hello' ).chmod( 0o755 )
    #NB: sb_foo_bar_hello is both script "bar_hello" of Foo and script "hello"
    #of Foo_Bar, so we use names which do not clash completely:
    res = run( 'sb -t', d )
    assert 'All tests completed without failures!' in res.out
    def check_foo_bar():
        res = run( 'sb -t', d )
        assert 'All tests completed without failures!' in res.out
        assert run( 'sbenv sb_foo_bar_bar_hello', d ).stdout.strip() == 'script Foo_Bar'
        assert run( 'sbenv sb_foo_bar_bar_app', d ).stdout.strip() == 'app Foo_Bar'
        testref = inst( d ) / 'tests' / 'testref' / 'sb_foo_bar_bar_hello.log'
        assert testref.is_symlink() and testref.exists()
    #Remove the scripts of Foo:
    shutil.rmtree( d / 'Foo' / 'scripts' )
    check_foo_bar()
    assert not ( inst( d ) / 'scripts' / 'sb_foo_bar_hello' ).exists()
    #Remove Foo completely:
    shutil.rmtree( d / 'Foo' )
    check_foo_bar()
    assert not os.path.lexists( inst( d ) / 'bin' / 'sb_foo_bar_app' )
    assert not os.path.lexists( inst( d ) / 'pkgs' / 'Foo' )
    assert not os.path.lexists( bld( d ) / 'named_targets' / 'Foo' )
    assert ( bld( d ) / 'named_targets' / 'Foo_Bar' ).is_dir()

def _apps_and_scripts_proj( d, pkgs, extra_files = None ):
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n' }
    for pkg in pkgs:
        files.update( {
            f'{pkg}/pkg.info' : 'package()\n',
            f'{pkg}/scripts/hello' : f'#!/usr/bin/env bash\necho script {pkg}\n',
            f'{pkg}/app_hi/main.cc' : ( '#include <cstdio>\nint main()'
                                        f' {{ std::printf("app {pkg}\\n"); return 0; }}\n' ),
        } )
    files.update( extra_files or {} )
    write_files( d, files )
    for pkg in pkgs:
        ( d / pkg / 'scripts' / 'hello' ).chmod( 0o755 )

def test_uninstall_does_not_need_db_info( tmp_path ):
    #Uninstalling a package must remove all its files, even if the package
    #database does not have complete info about them:
    import pickle
    import shutil
    d = tmp_path / 'proj'
    _apps_and_scripts_proj( d, ( 'Foo', 'Foo_Bar' ) )
    run( 'sb', d )
    dbfile = bld( d ) / 'globdb.pkl'
    with dbfile.open('rb') as fh:
        db = pickle.load( fh )
    #NB: Clearing other parts of the database (like pkg2parts) would trigger
    #reconfiguration of all packages, hiding any problems:
    db['pkg2runnables'].clear()
    with dbfile.open('wb') as fh:
        pickle.dump( db, fh )
    shutil.rmtree( d / 'Foo' )
    res = run( 'sb', d )
    #Foo_Bar must not be affected at all (in particular not rebuilt, which
    #would hide any problems):
    assert n_compiled( res.out ) == 0
    assert 'Foo_Bar' not in res.out.split('Summary:')[0]
    for f in ( 'bin/sb_foo_hi', 'scripts/sb_foo_hello', 'pkgs/Foo' ):
        assert not os.path.lexists( inst( d ) / f )
    assert run( 'sbenv sb_foo_bar_hi', d ).stdout.strip() == 'app Foo_Bar'
    assert run( 'sbenv sb_foo_bar_hello', d ).stdout.strip() == 'script Foo_Bar'

def test_user_files_never_removed( tmp_path ):
    #Files outside the cache dirs (here a package with symlinks to external
    #files and directories) must never be removed, no matter how the package
    #is removed from the cache:
    import shutil
    ext = tmp_path / 'external'
    ( ext / 'sub' ).mkdir( parents = True )
    ( ext / 'sub' / 'file.txt' ).write_text( 'precious' )
    ( ext / 'data.txt' ).write_text( 'precious data' )
    ( ext / 'inc' ).mkdir()
    ( ext / 'inc' / 'hdr.hh' ).write_text( 'inline int foo() { return 1; }\n' )
    ( ext / 'py' ).mkdir()
    ( ext / 'py' / 'extmod.py' ).write_text( 'value = 42\n' )
    def all_external_files():
        return sorted( ( str(f.relative_to(ext)), f.read_text() )
                       for f in ext.rglob('*') if f.is_file() )
    orig = all_external_files()
    d = tmp_path / 'proj'
    _apps_and_scripts_proj( d, ( 'Foo', ) )
    ( d / 'Foo' / 'data' ).mkdir()
    ( d / 'Foo' / 'data' / 'ext.txt' ).symlink_to( ext / 'data.txt' )
    ( d / 'Foo' / 'libinc' ).symlink_to( ext / 'inc' )
    ( d / 'Foo' / 'python' ).symlink_to( ext / 'py' )
    pkgfiles = sorted( str(f.relative_to(d)) for f in ( d / 'Foo' ).rglob('*') )
    def check_intact():
        assert all_external_files() == orig
        assert pkgfiles == sorted( str(f.relative_to(d))
                                   for f in ( d / 'Foo' ).rglob('*') )
    run( 'sb', d )
    assert ( inst( d ) / 'data' / 'Foo' / 'ext.txt' ).read_text() == 'precious data'
    assert run( [ 'sbenv', 'python3', '-c', 'import Foo.extmod as m; print(m.value)' ],
                d ).stdout.strip() == '42'
    check_intact()
    #Remove parts of the package (from the cache):
    for sd in ( 'libinc', 'data', 'python' ):
        ( d / 'Foo' / sd ).rename( d / f'{sd}_away' )
    run( 'sb', d )
    for sd in ( 'include', 'data', 'python' ):
        assert not os.path.lexists( inst( d ) / sd / 'Foo' )
    for sd in ( 'libinc', 'data', 'python' ):
        ( d / f'{sd}_away' ).rename( d / 'Foo' / sd )
    run( 'sb', d )
    check_intact()
    #Disable the package:
    cfg = d / 'simplebuild.cfg'
    cfgorig = cfg.read_text()
    cfg.write_text( cfgorig + '[build]\npkg_filter = ["!Foo"]\n' )
    res = run( 'sb', d )
    assert 'Uninstalling package Foo' in res.out
    assert not os.path.lexists( bld( d ) / 'pkgs' / 'Foo' )
    check_intact()
    cfg.write_text( cfgorig )
    run( 'sb', d )
    check_intact()
    #Move the package:
    ( d / 'sub' ).mkdir()
    ( d / 'Foo' ).rename( d / 'sub' / 'Foo' )
    run( 'sb', d )
    ( d / 'sub' / 'Foo' ).rename( d / 'Foo' )
    run( 'sb', d )
    check_intact()
    #Complete rebuilds and cleaning:
    run( 'sb -i', d )
    check_intact()
    run( 'sb -c', d )
    check_intact()
    #Remove the package completely (but external files must remain):
    run( 'sb', d )
    shutil.rmtree( d / 'Foo' )
    run( 'sb', d )
    assert all_external_files() == orig

def test_cache_from_other_simplebuild_version( proj ):
    #Caches with a different layout (here simulated by the absence of the
    #file with the layout version) are rebuilt from scratch:
    d = proj
    run( 'sb', d )
    ( bld( d ) / 'layout_version.txt' ).unlink()
    res = run( 'sb', d )
    assert 'cache directory was created by a different version' in res.out
    check_ok( d )
    res = run( 'sb', d )
    assert 'different version' not in res.out

def test_removed_libinc_uninstalled( tmp_path ):
    #The include dir of a package in the install area is a symlink, which must
    #be removed when the libinc dir of the package is removed:
    import shutil
    d = tmp_path / 'proj'
    write_files( d, { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
                      'Foo/pkg.info' : 'package()\n',
                      'Foo/libinc/foo.hh' : 'inline int foo() { return 1; }\n' } )
    run( 'sb', d )
    incdir = inst( d ) / 'include' / 'Foo'
    assert incdir.is_symlink() and ( incdir / 'foo.hh' ).exists()
    shutil.rmtree( d / 'Foo' / 'libinc' )
    run( 'sb', d )
    assert not os.path.lexists( incdir )

def _n_recreated( out ):
    return sum( 1 for line in out.splitlines()
                if 'Recreating pkg targets for' in line )

@pytest.mark.parametrize( 'errtype', [ 'pkg', 'global' ] )
def test_config_error_keeps_previous_build( proj, errtype ):
    #A configuration error must not destroy the previous build (which remains
    #usable), and once the error is fixed, only what is needed must be redone
    #(i.e. not all packages reconfigured or anything recompiled):
    d = proj
    if errtype == 'pkg':
        #Error in configuration of a single package:
        bad = d / 'PkgB' / 'app_hello' / 'bad.xyz'
        bad.write_text( 'bad\n' )
        errmsg = 'ERROR during configuration of package PkgB'
    else:
        #Error in loading of the packages:
        bad = d / 'PkgB' / 'pkg.info'
        orig = bad.read_text()
        bad.write_text( 'package(USEPKG PkgA NoSuchPkg)\n' )
        errmsg = 'NoSuchPkg'
    for i in range(2):
        res = run( 'sb', d, expect_ec = 1 )
        assert errmsg in res.out
        assert 'Traceback' not in res.out
        assert run( 'sbenv sb_pkgb_hello', d ).stdout.strip() == 'hello 17'
        assert ( inst( d ) / 'scripts' / 'sb_pkgb_testpy' ).exists()
    #Fix the error:
    if errtype == 'pkg':
        bad.unlink()
    else:
        bad.write_text( orig )
    res = run( 'sb --verbose', d )
    assert _n_recreated( res.out ) == 1
    assert 'Recreating pkg targets for PkgB' in res.out
    assert n_compiled( res.out ) == 0
    check_ok( d )

def test_ctrl_c_during_configuration( proj ):
    #CTRL-C during configuration (here: during the environment inspection via
    #CMake) must stop cleanly, leaving the previous build usable:
    import os
    import signal
    import subprocess
    from sbtestutils import clean_env
    d = proj
    p = subprocess.Popen( [ 'sb', '--examine' ], cwd = d, env = clean_env(),
                          start_new_session = True, stdout = subprocess.PIPE,
                          stderr = subprocess.STDOUT )
    for line in p.stdout:
        if b'Inspecting environment via CMake' in line:
            break
    os.killpg( p.pid, signal.SIGINT )
    out = p.communicate( timeout = 120 )[0].decode()
    assert p.returncode == 130
    assert 'Interrupted by user (CTRL-C).' in out
    assert 'Traceback' not in out and 'ERROR' not in out
    assert not ( bld( d ) / '.lock' ).exists()
    assert run( 'sbenv sb_pkgb_hello', d ).stdout.strip() == 'hello 17'
    res = run( 'sb', d )
    assert n_compiled( res.out ) == 0
    check_ok( d )

def test_stale_pkg_removed_without_db_info( tmp_path ):
    #Packages are removed from the cache when they are no longer enabled,
    #even if the package database does not know they were ever there:
    import pickle
    import shutil
    d = tmp_path / 'proj'
    _apps_and_scripts_proj( d, ( 'Foo', 'Foo_Bar' ) )
    run( 'sb', d )
    dbfile = bld( d ) / 'globdb.pkl'
    with dbfile.open('rb') as fh:
        db = pickle.load( fh )
    del db['enabled_pkgnames']
    with dbfile.open('wb') as fh:
        pickle.dump( db, fh )
    shutil.rmtree( d / 'Foo' )
    res = run( 'sb', d )
    assert 'Uninstalling package Foo\n' in res.out
    assert 'Uninstalling package Foo_Bar' not in res.out
    for f in ( 'bin/sb_foo_hi', 'scripts/sb_foo_hello', 'pkgs/Foo' ):
        assert not os.path.lexists( inst( d ) / f )
    for f in ( 'pc/Foo', 'pkgs/Foo', 'named_targets/Foo',
               'makefiles/Makefile_Foo.make' ):
        assert not os.path.lexists( bld( d ) / f )
    assert run( 'sbenv sb_foo_bar_hi', d ).stdout.strip() == 'app Foo_Bar'

@pytest.mark.parametrize( 'errtype', [ 'unknowndep', 'pkgcfg', 'pkgname' ] )
def test_errors_shown_in_quiet_mode( tmp_path, errtype ):
    #Errors must never be silent, so in quiet mode they are shown on stderr
    #(tools like ncdevtool run "sb --quiet" and only show stderr on failures):
    d = tmp_path / 'proj'
    write_files( d, _files )
    if errtype == 'unknowndep':
        ( d / 'PkgA' / 'pkg.info' ).write_text( 'package(USEPKG NoSuchPkg)\n' )
        expected = 'Unknown package "NoSuchPkg"'
    elif errtype == 'pkgcfg':
        ( d / 'PkgA' / 'pkg.info' ).write_text( 'package(USEEXT NoSuchExtDep)\n' )
        expected = 'NoSuchExtDep'
    else:
        #(Previously gave an AssertionError traceback):
        ( d / 'PkgA' ).rename( d / 'PA' )
        expected = 'Invalid package name: "PA"'
    for quiet in ( True, False ):
        res = run( [ 'sb' ] + ( [ '--quiet' ] if quiet else [] ), d, expect_ec = None )
        assert res.ec != 0
        assert 'Traceback' not in res.out
        assert expected in ( res.stderr if quiet else res.stdout )
        if quiet:
            assert not res.stdout

@pytest.mark.parametrize( 'quiet', [ False, True ] )
def test_python3_in_path_must_match( tmp_path, quiet ):
    #Code is built for the Python interpreter running simplebuild, and the
    #python3 command in the PATH must belong to the same installation or
    #environment (since scripts starting with "#!/usr/bin/env python3" must be
    #able to use the built code):
    import sys
    d = tmp_path / 'proj'
    write_files( d, _files )
    ( d / 'PkgB' / 'scripts' / 'testpy' ).chmod( 0o755 )
    bindir = tmp_path / 'fakebin'
    bindir.mkdir()
    f = bindir / 'python3'
    f.write_text( '#!/bin/sh\necho "wrong python" >&2\nexit 1\n' )
    f.chmod( 0o755 )
    cmd = [ 'sb' ] + ( [ '--quiet' ] if quiet else [] )
    res = run( cmd, d, env_extra = { 'PATH' : f'{bindir}:{clean_env()["PATH"]}' },
               expect_ec = 1 )
    assert 'is not from the same Python installation or environment' in res.out
    assert str(f) in res.out
    #Works once the PATH is fixed:
    res = run( 'sb -t', d )
    assert 'All tests completed without failures!' in res.out
    res = run( [ 'sbenv', sys.executable, '-c', 'import PkgB.cmod; print(PkgB.cmod.value())' ], d )
    assert res.stdout.strip() == '17'
