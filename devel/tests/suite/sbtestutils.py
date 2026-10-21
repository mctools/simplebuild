# Utilities for the pytest based simplebuild test suite.
#
# The tests always exercise the simplebuild installation which is active in
# the python environment running pytest (e.g. an editable "pip install -e" of a
# local clone, a regular pip install, or a conda package).
#
# Environment variables recognised (all optional, mostly intended for CI):
#
#   SBTEST_REQUIRE : Comma or space separated list of features which must be
#                    available (e.g. "shell:zsh,ncrystal,cppcheck,ruff"). Tests
#                    which would otherwise be skipped due to a missing feature
#                    will instead fail if the feature is listed here.
#   SBTEST_EXPECT_DISABLED_EXTDEPS : Space separated list of extdeps which must
#                    be reported as disabled by sb_core_extdeps.
#   SBTEST_LOGDIR  : If set, the commands invoked by the tests and their output
#                    are written to log files in this directory (one per test).

import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys

import pytest

reporoot = pathlib.Path(__file__).resolve().parent.parent.parent.parent
devel_tests_dir = reporoot / 'devel' / 'tests'
assert ( reporoot / 'pyproject.toml' ).is_file()
assert devel_tests_dir.is_dir()

def _split_list( s ):
    return [ e for e in re.split( r'[\s,]+', s or '' ) if e ]

def required_features():
    return set( _split_list( os.environ.get('SBTEST_REQUIRE') ) )

def require_feature( name, available, reason = None ):
    """Skip the test if the feature is not available, unless it is listed in
    SBTEST_REQUIRE, in which case the test fails instead."""
    if available:
        return
    testname = os.environ.get('PYTEST_CURRENT_TEST','').split(' ')[0]
    msg = ( f'Feature "{name}" not available'
            + ( f' ({reason})' if reason else '' )
            + ( f' in {testname}' if testname else '' ) )
    if name in required_features():
        pytest.fail( msg + ' but it is listed in SBTEST_REQUIRE' )
    pytest.skip( msg )

def expected_disabled_extdeps():
    return _split_list( os.environ.get('SBTEST_EXPECT_DISABLED_EXTDEPS') )

def clean_env( extra = None ):
    """Environment for invoking simplebuild commands, without any traces of
    previously activated simplebuild environments, and with the scripts of
    the python environment running pytest first in the PATH."""
    env = os.environ.copy()
    for k in list(env.keys()):
        if ( k.startswith('SBLD_') or k in ('_SIMPLEBUILD_CURRENT_ENV',
                                             'SIMPLEBUILD_CFG') ):
            del env[k]
    bindir = str( pathlib.Path(sys.executable).parent )
    env['PATH'] = bindir + ( ':' + env['PATH'] if env.get('PATH') else '' )
    if extra:
        env.update( extra )
    return env

class CmdResult:

    def __init__( self, cmd, ec, stdout, stderr ):
        self.cmd = cmd
        self.ec = ec
        self.stdout = stdout
        self.stderr = stderr

    @property
    def out( self ):
        """Combined stdout and stderr."""
        return self.stdout + self.stderr

def _logfile():
    logdir = os.environ.get('SBTEST_LOGDIR')
    if not logdir:
        return None
    testname = os.environ.get('PYTEST_CURRENT_TEST','unknown').split(' ')[0]
    testname = re.sub( r'[^A-Za-z0-9_.-]+', '_', testname )
    p = pathlib.Path(logdir)
    p.mkdir( parents = True, exist_ok = True )
    return p / f'{testname}.log'

def run( cmd, cwd, *, expect_ec = 0, env_extra = None ):
    """Run a command (string or list), check the exit code (unless expect_ec is
    None), and return a CmdResult. On unexpected exit codes, the test fails
    with the complete output of the command in the failure message."""
    cmdlist = shlex.split(cmd) if isinstance(cmd,str) else [str(e) for e in cmd]
    cmdstr = cmd if isinstance(cmd,str) else shlex.join(cmdlist)
    p = subprocess.run( cmdlist, cwd = cwd, env = clean_env( env_extra ),
                        capture_output = True, check = False )
    res = CmdResult( cmdstr, p.returncode,
                     p.stdout.decode(errors='replace'),
                     p.stderr.decode(errors='replace') )
    report = ( f'>>> {cmdstr}\n(in {cwd})\n'
               f'--- exit code: {res.ec}\n'
               f'--- stdout:\n{res.stdout}\n'
               f'--- stderr:\n{res.stderr}\n' )
    lf = _logfile()
    if lf:
        with lf.open('at') as fh:
            fh.write( report + '\n' )
    if expect_ec is not None and res.ec != expect_ec:
        pytest.fail( f'Command gave exit code {res.ec} (expected {expect_ec}):'
                     f'\n\n{report}', pytrace = False )
    return res

def run_bash( script, cwd, **kwargs ):
    """Run a snippet of bash code (with errexit and nounset enabled)."""
    return run( [ 'bash', '-eu', '-c', script ], cwd, **kwargs )

def summary_line( out, label ):
    """Extract value of a line in the sb build summary (or None)."""
    for line in out.splitlines():
        if re.match( r'^sbld:\s+' + re.escape(label) + r'\s+:', line ):
            return line.split(':',2)[2].strip()
    return None

def n_compiled( out ):
    """Number of compiled files in output of sb."""
    return sum( 1 for line in out.splitlines()
                if line.strip().startswith('Building ') )

def have_cmd( name ):
    return shutil.which( name, path = clean_env()['PATH'] ) is not None

def write_files( basedir, files ):
    """Write dictionary of { relpath : content } below basedir."""
    for relpath, content in files.items():
        f = basedir / relpath
        f.parent.mkdir( parents = True, exist_ok = True )
        f.write_text( content )

class PtyProcess:
    """Run a command in a pseudo terminal, for testing interactive (e.g.
    curses based) programs. The output is collected, and can be searched either
    as a stream of text (with escape codes removed), or as the content of the
    screen as it would be displayed (the latter requires the pyte module, and
    is needed for curses based programs, which only redraw changed parts of
    the screen)."""

    def __init__( self, cmd, cwd, rows = 30, cols = 140, env_extra = None ):
        import os
        import pty
        import struct
        import fcntl
        import termios
        env = clean_env( env_extra )
        env['TERM'] = 'xterm'
        env['LINES'], env['COLUMNS'] = str(rows), str(cols)
        env['LANG'] = env['LC_ALL'] = 'C.UTF-8'
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            #Set the terminal size before the program starts:
            fcntl.ioctl( 0, termios.TIOCSWINSZ,
                         struct.pack( 'HHHH', rows, cols, 0, 0 ) )
            os.chdir( cwd )
            os.execvpe( cmd[0], cmd, env )
        self.raw = b''
        self.ec = None
        self._pos = 0
        self._rows, self._cols = rows, cols
        self._screen = None

    @property
    def text( self ):
        #Screen output with escape sequences removed (not an exact rendering
        #of the screen, but good enough for finding text):
        t = self.raw.decode( 'utf-8', errors = 'replace' )
        t = re.sub( r'\x1b\[[0-9;?]*[A-Za-z]', ' ', t )
        return re.sub( r'\x1b[()][A-Za-z0-9]|\x1b[=>]|\x0f|\x0e', '', t )

    def _read( self, timeout ):
        import os
        import select
        r, _, _ = select.select( [ self.fd ], [], [], timeout )
        if not r:
            return False
        try:
            data = os.read( self.fd, 65536 )
        except OSError:
            data = b''
        if not data:
            self._reap()
            return False
        self.raw += data
        return True

    def _reap( self ):
        import os
        if self.ec is None:
            _, status = os.waitpid( self.pid, 0 )
            self.ec = os.waitstatus_to_exitcode( status )

    def wait_for( self, pattern, timeout = 60 ):
        """Wait for regex pattern to appear in the output after the end of
        the previous match (like the "expect" command), and return the
        match."""
        import time
        t0 = time.time()
        while True:
            m = re.compile( pattern ).search( self.text, self._pos )
            if m:
                self._pos = m.end()
                return m
            if self.ec is not None or time.time() - t0 > timeout:
                raise AssertionError( f'Pattern {pattern!r} not found. Output:\n'
                                      + self.text[-3000:] )
            self._read( 0.2 )

    def screen( self ):
        """The current content of the screen (requires pyte)."""
        try:
            import pyte
        except ImportError:
            #NB: Never skip tests due to missing test dependencies, since we
            #would then be running blind:
            pytest.fail( 'The pyte module is required for this test (install'
                         ' the test dependencies, e.g. with "pip install'
                         ' simple-build-system[test]")', pytrace = False )
        if self._screen is None:
            self._screen = pyte.Screen( self._cols, self._rows )
            self._stream = pyte.ByteStream( self._screen )
            self._nfed = 0
        self._stream.feed( self.raw[self._nfed:] )
        self._nfed = len( self.raw )
        return '\n'.join( line.rstrip() for line in self._screen.display )

    def wait_for_screen( self, pattern, timeout = 60 ):
        """Wait for regex pattern to appear on the screen, and return the
        match."""
        import time
        t0 = time.time()
        while True:
            self._read( 0.1 )
            m = re.compile( pattern ).search( self.screen() )
            if m:
                return m
            if self.ec is not None or time.time() - t0 > timeout:
                raise AssertionError( f'Pattern {pattern!r} not found on'
                                      ' screen:\n' + self.screen() )

    def send( self, keys ):
        import os
        import time
        os.write( self.fd, keys.encode() if isinstance( keys, str ) else keys )
        time.sleep( 0.1 )

    def wait_exit( self, timeout = 60 ):
        import time
        t0 = time.time()
        while self.ec is None:
            if time.time() - t0 > timeout:
                raise AssertionError( 'Process did not exit. Output:\n'
                                      + self.text[-3000:] )
            self._read( 0.2 )
        return self.ec
