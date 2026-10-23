# Tests of bundles with a dynamic_generator script (as used for instance by the
# development tools of NCrystal, which generate packages in this manner). See
# also test_integration_devtool_workflow.py.

import json
import shutil
import subprocess
import pytest

from sbtestutils import run, write_files, clean_env

pytestmark = pytest.mark.integration

#The generator is controlled by a genspec.json file next to it, and logs each
#invocation to genlog.jsonl:
_generator = r'''
import json
import os
import pathlib
import shutil
import sys
import time
d = pathlib.Path(__file__).resolve().parent
spec = json.loads( ( d / 'genspec.json' ).read_text() )
with ( d / 'genlog.jsonl' ).open('a') as fh:
    fh.write( json.dumps( dict( argv = sys.argv[1:], cwd = os.getcwd(),
                                isolated = sys.flags.isolated,
                                no_bytecode = sys.flags.dont_write_bytecode ) ) + '\n' )
#Detect overlapping invocations:
busy = d / 'generator_busy'
if busy.exists():
    print( 'overlapping invocations of the generator', file = sys.stderr )
    raise SystemExit(3)
busy.touch()
try:
    print( spec.get( 'stdout', 'message from the generator on stdout' ) )
    if spec.get('fail'):
        print( 'message from the failing generator on stderr', file = sys.stderr )
        raise SystemExit( spec['fail'] )
    time.sleep( spec.get( 'sleep', 0 ) )
    #(Re)create everything (like a non-incremental generator would):
    for subdir, content in ( ( 'pkgs', spec.get('pkgs',{}) ),
                             ( 'extdeps', spec.get('extdeps',{}) ) ):
        root = d / 'autogen' / subdir
        if root.exists():
            shutil.rmtree( root )
        for relpath, text in content.items():
            f = root / relpath
            f.parent.mkdir( parents = True, exist_ok = True )
            f.write_text( text )
            if '/scripts/' in relpath and not relpath.endswith('.log'):
                f.chmod( 0o755 )
finally:
    busy.unlink()
'''

_cfg_dyn = '''[bundle]
  name = 'mydyn'
  dynamic_generator = './gen.py'
  pkg_root = './autogen/pkgs'
  extdep_root = './autogen/extdeps'
'''

def _script( text ):
    return f'#!/usr/bin/env bash\necho "{text}"\n'

def _extdep( name, present ):
    return f'''set(HAS_{name} {1 if present else 0})
set(ExtDep_{name}_VERSION "1.2.3")
set(ExtDep_{name}_PREPEND_COMPILE_FLAGS "")
set(ExtDep_{name}_PREPEND_LINK_FLAGS "")
'''

class DynProject:

    def __init__( self, root ):
        self.root = root
        self.cache = root / 'simplebuild_cache'
        self.inst = self.cache / 'install'

    def set_spec( self, **spec ):
        ( self.root / 'genspec.json' ).write_text( json.dumps( spec ) )

    def log( self, clear = True ):
        f = self.root / 'genlog.jsonl'
        if not f.exists():
            return []
        res = [ json.loads(line) for line in f.read_text().splitlines() ]
        if clear:
            f.unlink()
        return res

    def run( self, cmd, **kw ):
        return run( cmd, self.root, **kw )

@pytest.fixture
def dynproj( tmp_path ):
    root = tmp_path / 'proj'
    #NB: autogen/pkgs does not exist initially (like in a fresh clone):
    write_files( root, { 'simplebuild.cfg' : _cfg_dyn,
                         'gen.py' : _generator } )
    p = DynProject( root )
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package()\n',
                         'GenA/scripts/hello' : _script('hello from GenA') } )
    return p

def test_generator_invocation( dynproj ):
    p = dynproj
    res = p.run( 'sb' )
    assert 'message from the generator on stdout' in res.stdout
    log = p.log()
    assert len(log) == 1
    #Arguments are the installation directory and the build mode, and the
    #script is run in isolated mode, without writing .pyc files:
    assert log[0]['argv'] == [ str(p.inst), 'release' ]
    assert log[0]['isolated'] and log[0]['no_bytecode']
    assert log[0]['cwd'] == str(p.root)
    assert not list( p.root.rglob('__pycache__') )
    assert ( p.inst / 'scripts' / 'sb_gena_hello' ).exists()
    #The arguments reflect the build variant:
    p.run( 'sb -d' )
    assert p.log()[0]['argv'] == [ str(p.cache / 'install_debug'), 'debug' ]
    #Commands launched from a subdirectory:
    sub = p.root / 'autogen' / 'pkgs' / 'GenA'
    run( 'sbenv sb_gena_hello', sub )
    assert p.log()[0]['cwd'] == str(sub)

def test_generator_invoked_by_all_commands( dynproj ):
    #The generator is invoked whenever simplebuild needs the configuration, but
    #its output must not end up in the output of sbenv/sbrun commands (or in
    #the output of "sb --env-setup", which is evaluated by shells):
    p = dynproj
    p.run( 'sb --quiet' )
    assert len( p.log() ) == 1
    for cmd in ( 'sbenv sb_gena_hello', 'sbrun sb_gena_hello' ):
        res = p.run( cmd )
        assert res.stdout == 'hello from GenA\n'
        assert len( p.log() ) == 1
    res = p.run( 'sb --env-setup' )
    assert 'message from the generator' not in res.stdout
    assert len( p.log() ) == 1
    for cmd in ( 'sb --help', 'sb --version' ):
        p.run( cmd )
        assert not p.log()

@pytest.mark.parametrize( 'quiet', [ False, True ] )
def test_failing_generator( dynproj, quiet ):
    p = dynproj
    p.run( 'sb --quiet' )
    p.set_spec( fail = 7 )
    res = p.run( [ 'sb' ] + ( [ '--quiet' ] if quiet else [] ), expect_ec = 1 )
    #Without --quiet, all output (including that of the generator and the
    #error message) is on stdout, in the right order. With --quiet, it is
    #shown on stderr (tools like ncdevtool only show the stderr output of "sb
    #--quiet"):
    out = res.stderr if quiet else res.stdout
    assert not ( res.stdout if quiet else res.stderr )
    i1 = out.index( 'message from the generator on stdout' )
    i2 = out.index( 'message from the failing generator on stderr' )
    i3 = out.index( 'gen.py from mydyn failed (exit code 7)' )
    assert i1 < i2 < i3
    #Commands are not launched if the generator fails:
    for cmd in ( 'sbenv sb_gena_hello', 'sbrun sb_gena_hello' ):
        res = p.run( cmd, expect_ec = 1 )
        assert 'hello' not in res.stdout
        assert 'message from the failing generator on stderr' in res.stderr
        assert 'gen.py from mydyn failed (exit code 7)' in res.stderr
    #Everything works again when the generator is fixed:
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package()\n',
                         'GenA/scripts/hello' : _script('hello again') } )
    assert p.run( 'sbrun sb_gena_hello' ).stdout == 'hello again\n'

def test_generated_packages_change( dynproj ):
    p = dynproj
    p.run( 'sb --quiet' )
    #A package is added, which depends on another generated package, and
    #which has a test:
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package()\n',
                         'GenA/scripts/hello' : _script('hello from GenA'),
                         'GenB/pkg.info' : 'package(USEPKG GenA)\n',
                         'GenB/scripts/testb' : _script('test of GenB'),
                         'GenB/scripts/testb.log' : 'test of GenB\n' } )
    res = p.run( 'sb -t' )
    assert 'All tests completed without failures!' in res.out
    assert ( p.inst / 'scripts' / 'sb_genb_testb' ).exists()
    #A package is removed, so its files disappear from the installation, and
    #its tests are no longer run:
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package()\n',
                         'GenA/scripts/hello' : _script('hello from GenA'),
                         'GenA/scripts/testa' : _script('test of GenA') } )
    res = p.run( 'sb -t' )
    assert 'All tests completed without failures!' in res.out
    assert not ( p.inst / 'scripts' / 'sb_genb_testb' ).exists()
    assert ( p.inst / 'scripts' / 'sb_gena_testa' ).exists()
    res = p.run( 'sb --testreport' )
    assert 'sb_gena_testa' in res.out and 'sb_genb_testb' not in res.out

def test_generated_extdeps( dynproj ):
    #The generator can also create definitions of external dependencies in the
    #extdep_root of the bundle (NCrystal creates definitions for some optional
    #Python modules in this manner):
    p = dynproj
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package(USEEXT GenDepYes)\n',
                         'GenA/scripts/hello' : _script('hello from GenA'),
                         'GenB/pkg.info' : 'package(USEEXT GenDepNo)\n',
                         'GenB/scripts/hello' : _script('hello from GenB') },
                extdeps = { 'ExtDep_GenDepYes.cmake' : _extdep('GenDepYes',True),
                            'ExtDep_GenDepNo.cmake' : _extdep('GenDepNo',False) } )
    res = p.run( 'sb' )
    assert ( p.inst / 'scripts' / 'sb_gena_hello' ).exists()
    assert not ( p.inst / 'scripts' / 'sb_genb_hello' ).exists()
    assert 'GenDepNo' in res.out
    #The dependency becomes available:
    p.set_spec( pkgs = { 'GenB/pkg.info' : 'package(USEEXT GenDepNo)\n',
                         'GenB/scripts/hello' : _script('hello from GenB') },
                extdeps = { 'ExtDep_GenDepNo.cmake' : _extdep('GenDepNo',True) } )
    assert p.run( 'sbrun sb_genb_hello' ).stdout == 'hello from GenB\n'
    assert not ( p.inst / 'scripts' / 'sb_gena_hello' ).exists()

def test_concurrent_invocations( dynproj ):
    #Simultaneous invocations of sbenv (e.g. in different terminals) must not
    #lead to simultaneous invocations of the generator, since generators
    #typically remove and create files:
    p = dynproj
    p.run( 'sb --quiet' )
    p.log()
    p.set_spec( pkgs = { 'GenA/pkg.info' : 'package()\n',
                         'GenA/scripts/hello' : _script('hello from GenA') },
                sleep = 0.3 )
    procs = [ subprocess.Popen( [ 'sbenv', 'sb_gena_hello' ], cwd = p.root,
                                env = clean_env(), stdout = subprocess.PIPE,
                                stderr = subprocess.STDOUT )
              for i in range(4) ]
    outs = [ ( pr.communicate()[0].decode(), pr.returncode ) for pr in procs ]
    assert all( o == ( 'hello from GenA\n', 0 ) for o in outs ), outs
    assert len( p.log() ) == 4

def test_shared_and_multiple_generators( tmp_path ):
    #Two bundles with the same generator script lead to a single invocation,
    #while different scripts are all invoked:
    root = tmp_path / 'proj'
    gen = '''import pathlib, sys
d = pathlib.Path(__file__).resolve().parent
with ( d.parent / 'genlog.txt' ).open('a') as fh:
    fh.write( f'{d.name}/{pathlib.Path(__file__).name}\\n' )
'''
    write_files( root, {
        'simplebuild.cfg' : ( "[bundle]\n  name = 'main'\n[depend]\n"
                              "  bundles = [ 'b1', 'b2', 'b3' ]\n"
                              "  search_path = [ './b1', './b2', './b3' ]\n" ),
        'b1/simplebuild.cfg' : "[bundle]\n  name = 'b1'\n  dynamic_generator = './gen.py'\n",
        'b1/gen.py' : gen,
        'b1/PkgB1/pkg.info' : 'package()\n',
        'b2/PkgB2/pkg.info' : 'package()\n',
        'b3/PkgB3/pkg.info' : 'package()\n',
        'b2/simplebuild.cfg' : "[bundle]\n  name = 'b2'\n  dynamic_generator = '../b1/gen.py'\n",
        'b3/simplebuild.cfg' : "[bundle]\n  name = 'b3'\n  dynamic_generator = './gen.py'\n",
        'b3/gen.py' : gen,
    } )
    run( 'sb --quiet', root )
    assert sorted( ( root / 'genlog.txt' ).read_text().split() ) == [ 'b1/gen.py', 'b3/gen.py' ]

@pytest.mark.parametrize( 'name,content,errmsg', [
    ( 'gen.txt', 'print(1)\n', 'dynamic_generator script name must end in .py' ),
    ( None, None, 'must refer to an existing file' ),
] )
def test_invalid_generator( tmp_path, name, content, errmsg ):
    root = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : ( "[bundle]\n  name = 'mydyn'\n"
                                    f"  dynamic_generator = './{name or 'missing.py'}'\n" ) }
    if name:
        files[name] = content
    write_files( root, files )
    for cmd in ( 'sb', 'sbenv true' ):
        res = run( cmd, root, expect_ec = 1 )
        assert errmsg in res.out

def test_generator_uses_python_of_simplebuild( dynproj ):
    #The generator is run with the same Python interpreter as simplebuild
    #itself (and not whatever "python3" happens to be first in the PATH):
    p = dynproj
    gen = p.root / 'gen.py'
    gen.write_text( 'import sys, pathlib\n'
                    'pathlib.Path(__file__).with_name("pyexec.txt").write_text(sys.executable)\n'
                    + gen.read_text() )
    bindir = p.root / 'fakebin'
    bindir.mkdir()
    for n in ( 'python', 'python3' ):
        f = bindir / n
        f.write_text( '#!/bin/sh\necho "wrong python" >&2\nexit 1\n' )
        f.chmod( 0o755 )
    env = clean_env()
    p.run( 'sb --quiet' )
    run( 'sbenv true', p.root, env_extra = { 'PATH' : f'{bindir}:{env["PATH"]}' } )
    sbpy = shutil.which( 'sb', path = env['PATH'] )
    assert sbpy
    used = ( p.root / 'pyexec.txt' ).read_text()
    assert used != str( bindir / 'python3' )
    assert used == _python_of_script( sbpy )

def _python_of_script( path ):
    """The Python interpreter used by a console script (as reported by the
    interpreter itself)."""
    first = open( path, 'rb' ).readline().decode().strip()
    assert first.startswith('#!')
    interp = first[2:].split()[0]
    return subprocess.run( [ interp, '-c', 'import sys; print(sys.executable)' ],
                           capture_output = True, check = True ).stdout.decode().strip()
