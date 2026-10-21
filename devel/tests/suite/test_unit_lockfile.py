import os
import subprocess
import time

import pytest

from _simple_build_system import lockfile

pytestmark = pytest.mark.unit

def dead_pid():
    p = subprocess.Popen( [ 'true' ] )
    p.wait()
    assert not lockfile.pid_is_alive( p.pid )
    return p.pid

@pytest.fixture
def live_process():
    p = subprocess.Popen( [ 'sleep', '60' ] )
    yield p
    p.kill()
    p.wait()

def test_parse_lock_content():
    parse = lockfile.parse_lock_content
    assert parse( '123@somehost@bootid-1' ) == ( 123, 'somehost', 'bootid-1' )
    assert parse( '123@somehost' ) == ( 123, 'somehost', None )
    assert parse( ' 123@some.host.org\n' ) == ( 123, 'some.host.org', None )
    assert parse( '123' ) == ( 123, None, None )#old simplebuild versions
    for bad in ( '', 'abc', '123@', '@host', '-5@host', '0', None,
                 '123@host@', '123@@boot', '1@2@3@4' ):
        assert parse( bad ) == ( None, None, None )

def test_lock_content():
    pid, host, bootid = lockfile.parse_lock_content( lockfile.lock_content() )
    assert pid == os.getpid() and host == lockfile._hostname()
    assert bootid == lockfile._boot_id()
    assert bootid is not None#available on all supported platforms

def test_pid_is_alive( live_process ):
    assert lockfile.pid_is_alive( os.getpid() )
    assert lockfile.pid_is_alive( live_process.pid )
    assert not lockfile.pid_is_alive( dead_pid() )

def test_acquire_release( tmp_path ):
    lf = tmp_path / '.lock'
    ok, content = lockfile.acquire( lf )
    assert ok
    assert lf.read_text() == content == lockfile.lock_content()
    assert lockfile.is_locked( lf )
    #Can not acquire again (lock held by a live process, i.e. ourselves):
    ok2, info = lockfile.acquire( lf )
    assert not ok2
    assert info.pid == os.getpid()
    #Description includes the command of the process holding the lock:
    assert info.describe().startswith( f'by process {os.getpid()}: "' )
    assert 'running for' in info.describe()
    lockfile.release( lf, content )
    assert not lf.exists()
    assert not lockfile.is_locked( lf )
    #Releasing again is harmless:
    lockfile.release( lf, content )

def test_release_only_own_lock( tmp_path ):
    lf = tmp_path / '.lock'
    lf.write_text( 'somebody@else' )
    lockfile.release( lf, lockfile.lock_content() )
    assert lf.read_text() == 'somebody@else'

def test_live_lock_from_other_process( tmp_path, live_process ):
    lf = tmp_path / '.lock'
    lf.write_text( f'{live_process.pid}@{lockfile._hostname()}' )
    ok, info = lockfile.acquire( lf )
    assert not ok and info.pid == live_process.pid
    assert lockfile.is_locked( lf )

def test_stale_lock_is_removed( tmp_path ):
    lf = tmp_path / '.lock'
    pid = dead_pid()
    lf.write_text( f'{pid}@{lockfile._hostname()}' )
    assert not lockfile.is_locked( lf )
    removed = []
    ok, content = lockfile.acquire( lf, on_stale_removal = removed.append )
    assert ok and lf.read_text() == content
    assert len(removed) == 1 and removed[0].pid == pid
    assert removed[0].describe() == f'by process {pid}'

def test_lock_from_before_reboot_is_stale( tmp_path, live_process ):
    #A lock from a previous boot is stale, even if a process with the same pid
    #happens to exist now:
    lf = tmp_path / '.lock'
    host = lockfile._hostname()
    lf.write_text( f'{live_process.pid}@{host}@some-old-bootid' )
    assert not lockfile.is_locked( lf )
    ok, content = lockfile.acquire( lf )
    assert ok
    lockfile.release( lf, content )
    #Same boot: not stale:
    lf.write_text( f'{live_process.pid}@{host}@{lockfile._boot_id()}' )
    assert lockfile.is_locked( lf )
    #No boot id (fall back to checking the pid):
    lf.write_text( f'{live_process.pid}@{host}' )
    assert lockfile.is_locked( lf )

def test_lock_from_other_host_never_stale( tmp_path ):
    lf = tmp_path / '.lock'
    lf.write_text( f'{dead_pid()}@some-other-host-{os.getpid()}' )
    ok, info = lockfile.acquire( lf )
    assert not ok
    assert 'on host some-other-host' in info.describe()
    assert lockfile.is_locked( lf )

def test_old_format_lock_never_stale( tmp_path ):
    #Lock files from older simplebuild versions contain only the pid, so we
    #can not know if they were created on this host:
    lf = tmp_path / '.lock'
    lf.write_text( str( dead_pid() ) )
    ok, info = lockfile.acquire( lf )
    assert not ok and info.host is None

def test_unparsable_lock( tmp_path ):
    lf = tmp_path / '.lock'
    lf.write_text( '' )
    #Recently created: might be about to be written by another process:
    ok, info = lockfile.acquire( lf )
    assert not ok and info.pid is None
    assert info.describe() == 'by an unknown process'
    #Old: considered stale:
    t = time.time() - 3600
    os.utime( lf, ( t, t ) )
    ok, content = lockfile.acquire( lf )
    assert ok and lf.read_text() == content

def test_exit_cleanly_on_termination_signals( tmp_path ):
    #A process holding a lock which receives SIGTERM or SIGHUP must release the
    #lock (by running atexit handlers):
    import signal
    import sys
    lf = tmp_path / '.lock'
    script = tmp_path / 'holdlock.py'
    script.write_text(
        'import atexit, pathlib, sys, time\n'
        'from _simple_build_system import lockfile\n'
        'lockfile.exit_cleanly_on_termination_signals()\n'
        'lf = pathlib.Path(sys.argv[1])\n'
        'ok, content = lockfile.acquire( lf )\n'
        'assert ok\n'
        'atexit.register( lambda : lockfile.release( lf, content ) )\n'
        'print("locked", flush=True)\n'
        'time.sleep(60)\n' )
    for sig in ( signal.SIGTERM, signal.SIGHUP ):
        p = subprocess.Popen( [ sys.executable, str(script), str(lf) ],
                              stdout = subprocess.PIPE )
        assert p.stdout.readline().strip() == b'locked'
        assert lf.exists()
        p.send_signal( sig )
        assert p.wait( timeout = 30 ) == 128 + sig
        p.stdout.close()
        assert not lf.exists()

def test_boot_id():
    #A random UUID generated by the kernel at boot, so it is stable:
    import re
    import sys
    b = lockfile._calc_boot_id()
    assert b == lockfile._calc_boot_id() == lockfile._boot_id()
    assert re.match( '^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}'
                     '-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$', b )
    if sys.platform == 'darwin':
        assert lockfile._sysctl_string( b'kern.bootsessionuuid' ) == b
        assert lockfile._sysctl_string( b'no.such.sysctl.name' ) is None
