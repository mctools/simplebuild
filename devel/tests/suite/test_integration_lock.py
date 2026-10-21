# The lock preventing concurrent sb invocations on the same cache directory,
# and query options (issues #72 and #30 on GitHub).

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

#Script reporting whether the lock of the cache dir is currently held. With
#the "--require" argument, it fails if not (making it suitable as a test):
_checklock_script = '''#!/usr/bin/env python3
import os
import pathlib
import sys
inst = pathlib.Path(os.environ['SBLD_INSTALL_PREFIX'])
lockfile = inst.parent / inst.name.replace('install','bld',1) / '.lock'
locked = lockfile.exists()
print('LOCKED' if locked else 'UNLOCKED')
if '--require' in sys.argv[1:] and not locked:
    raise SystemExit(1)
'''

@pytest.fixture
def lockproj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/checklock' : _checklock_script,
        'MyPkg/scripts/testlockheld' : '#!/usr/bin/env bash\nexec sb_mypkg_checklock --require\n',
    } )
    for f in ( 'checklock', 'testlockheld' ):
        ( d / 'MyPkg' / 'scripts' / f ).chmod( 0o755 )
    return d

def test_lock_held_during_build_and_tests( lockproj ):
    d = lockproj
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    run( 'sb -t', d )
    assert not lockfile.exists()
    #The lock must also be held after the cache dir is wiped by --insist:
    run( 'sb -t --insist', d )
    assert not lockfile.exists()
    #Also in other variants:
    run( 'sb -d -t --insist', d )
    assert not ( d / 'simplebuild_cache' / 'bld_debug' / '.lock' ).exists()

def test_sbrun_releases_lock( lockproj ):
    #Issue #72: sbrun must release the lock before launching the command, so
    #other sb invocations can proceed while the command runs:
    d = lockproj
    res = run( 'sbrun sb_mypkg_checklock', d )
    assert res.stdout.strip() == 'UNLOCKED'
    res = run( 'sbrun -d sb_mypkg_checklock', d )
    assert res.stdout.strip() == 'UNLOCKED'
    res = run( [ 'sbrun', 'bash', '-c', 'sb -q && echo NESTED_SB_OK' ], d )
    assert 'NESTED_SB_OK' in res.stdout

def test_competing_invocation_detected( lockproj ):
    d = lockproj
    run( 'sb', d )
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    lockfile.write_text( '999999999' )
    res = run( 'sb', d, expect_ec = 1 )
    assert 'Presence of lock file indicates competing invocation' in res.out
    run( 'sb --removelock', d )
    assert not lockfile.exists()

def test_pkginfo_case_insensitive( lockproj ):
    #Issue #30: package names are unique when ignoring case, so --pkginfo can
    #be relaxed about casing:
    d = lockproj
    for name in ( 'MyPkg', 'mypkg', 'MYPKG', 'myPKG' ):
        res = run( [ 'sb', '--pkginfo', name ], d )
        assert 'Package name            : MyPkg' in res.out
    res = run( 'sb --pkginfo nosuchpkg', d, expect_ec = 1 )
    assert 'Unknown package "nosuchpkg"' in res.out

def test_stale_lock_removed_automatically( lockproj ):
    #A lock left behind by a process which no longer exists (e.g. killed with
    #SIGKILL) is removed automatically:
    import socket
    import subprocess
    d = lockproj
    run( 'sb', d )
    p = subprocess.Popen( [ 'true' ] )
    p.wait()
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    lockfile.write_text( f'{p.pid}@{socket.gethostname()}' )
    res = run( 'sb', d )
    assert 'Removing stale lock file' in res.out
    assert not lockfile.exists()

def test_sigterm_releases_lock( lockproj, tmp_path ):
    #When sb is terminated (e.g. by closing the terminal), it must not leave
    #the lock behind:
    import signal
    import subprocess
    import time
    from sbtestutils import clean_env
    d = lockproj
    marker = tmp_path / 'test_started'
    write_files( d, { 'MyPkg/scripts/testslow' :
                      f'#!/usr/bin/env bash\ntouch {marker}\nsleep 20\n' } )
    ( d / 'MyPkg' / 'scripts' / 'testslow' ).chmod( 0o755 )
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    for sig in ( signal.SIGTERM, signal.SIGHUP ):
        if marker.exists():
            marker.unlink()
        p = subprocess.Popen( [ 'sb', '-t' ], cwd = d, env = clean_env(),
                              stdout = subprocess.DEVNULL,
                              stderr = subprocess.DEVNULL )
        t0 = time.time()
        while not marker.exists():
            assert time.time() - t0 < 300, 'test did not start'
            assert p.poll() is None, 'sb ended prematurely'
            time.sleep(0.1)
        assert lockfile.exists()
        p.send_signal( sig )
        assert p.wait( timeout = 60 ) == 128 + sig
        assert not lockfile.exists()

def _start_in_own_process_group( cmd, cwd ):
    #Start command as a terminal would do with a foreground job, so we can send
    #signals to the whole process group (like pressing CTRL-C):
    import subprocess
    from sbtestutils import clean_env
    return subprocess.Popen( cmd, cwd = cwd, env = clean_env(),
                             start_new_session = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT )

def _ctrl_c( p ):
    import os
    import signal
    os.killpg( p.pid, signal.SIGINT )

def _wait_for_file( f, p, timeout = 300 ):
    import time
    t0 = time.time()
    while not f.exists():
        assert time.time() - t0 < timeout, f'timeout waiting for {f}'
        assert p.poll() is None, 'process ended prematurely'
        time.sleep( 0.05 )

def test_ctrl_c_during_tests( lockproj, tmp_path ):
    #CTRL-C during tests must stop everything promptly and cleanly: no test
    #summary, no traceback, no orphaned processes producing output, no lock:
    import time
    d = lockproj
    marks = tmp_path / 'marks.log'
    for i in range(3):
        write_files( d, { f'MyPkg/scripts/testslow{i}' :
                          '#!/usr/bin/env bash\nfor i in $(seq 1 100); do\n'
                          f'  echo "test{i} $i" >> {marks}\n  sleep 0.1\ndone\n' } )
        ( d / 'MyPkg' / 'scripts' / f'testslow{i}' ).chmod( 0o755 )
    run( 'sb', d )
    p = _start_in_own_process_group( [ 'sb', '-t', '--testexcerpts=5' ], d )
    _wait_for_file( marks, p )
    time.sleep( 0.5 )
    _ctrl_c( p )
    out = p.communicate( timeout = 60 )[0].decode()
    assert p.returncode == 130
    assert 'Interrupted by user (CTRL-C).' in out
    assert 'Traceback' not in out
    assert 'Test job results' not in out
    n = len( marks.read_text().splitlines() )
    time.sleep( 1.0 )
    assert len( marks.read_text().splitlines() ) == n, 'orphaned processes'
    assert not ( d / 'simplebuild_cache' / 'bld' / '.lock' ).exists()
    #Everything still works afterwards:
    res = run( 'sb -t --testfilter=sb_mypkg_testlockheld', d )
    assert 'All tests completed without failures!' in res.out

def test_ctrl_c_during_build( lockproj ):
    d = lockproj
    for i in range(20):
        write_files( d, { f'MyPkg/app_a{i}/main.cc' :
                          '#include <iostream>\n#include <map>\n#include <vector>\n'
                          'int main() { std::map<int,std::vector<int>> m;'
                          ' std::cout << m.size() << std::endl; return 0; }\n' } )
    p = _start_in_own_process_group( [ 'sb', '-j1' ], d )
    for line in p.stdout:
        if b'Building' in line:
            break
    _ctrl_c( p )
    out = p.communicate( timeout = 120 )[0].decode()
    assert p.returncode == 130
    assert 'Interrupted by user (CTRL-C).' in out
    assert 'Traceback' not in out
    assert not ( d / 'simplebuild_cache' / 'bld' / '.lock' ).exists()
    run( 'sb', d )
    assert run( 'sbenv sb_mypkg_a7', d ).stdout.strip() == '0'

def test_ctrl_c_in_sbenv_program( lockproj, tmp_path ):
    #CTRL-C in a program launched with sbenv just ends it (exit code 130, and
    #no extra output from sbenv):
    d = lockproj
    run( 'sb', d )
    marker = tmp_path / 'started'
    p = _start_in_own_process_group(
        [ 'sbenv', 'bash', '-c', f'touch {marker}; sleep 60' ], d )
    _wait_for_file( marker, p )
    _ctrl_c( p )
    out = p.communicate( timeout = 60 )[0].decode()
    assert p.returncode == 130
    assert out == ''

def test_lock_message_describes_holder( lockproj ):
    #The error message about a held lock must say which process holds it:
    import subprocess
    from _simple_build_system import lockfile as lf
    d = lockproj
    run( 'sb', d )
    holder = subprocess.Popen( [ 'sleep', '60' ] )
    try:
        lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
        c = f'{holder.pid}@{lf._hostname()}@{lf._boot_id()}'
        lockfile.write_text( c )
        res = run( 'sb', d, expect_ec = 1 )
        assert f'by process {holder.pid}: "sleep 60", running for' in res.out
        assert lockfile.read_text() == c
    finally:
        holder.kill()
        holder.wait()
    #Now the holder is gone, so the lock is stale:
    res = run( 'sb', d )
    assert 'Removing stale lock file' in res.out
