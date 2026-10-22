# Placing the cache directories under the directory given by the
# SIMPLEBUILD_CACHE_ROOT environment variable.

import hashlib

import pytest

from sbtestutils import n_compiled, run, write_files

pytestmark = pytest.mark.integration

def _write_proj( d, name = 'myproj', extra_cfg = '' ):
    write_files( d, { 'simplebuild.cfg' : ( f'[bundle]\nname = "{name}"\n' if name
                                            else '[bundle]\n' ) + extra_cfg,
                      'MyPkg/pkg.info' : 'package()\n',
                      'MyPkg/app_hello/main.cc' : '#include <cstdio>\nint main() { std::printf("hello\\n"); return 0; }\n' } )
    return d

def _expected_cachedir( root, proj, name ):
    cfg = str( ( proj / 'simplebuild.cfg' ).resolve() )
    return root / f'sb_{name}_{hashlib.sha256(cfg.encode()).hexdigest()[:12]}'

def _env( value ):
    return { 'SIMPLEBUILD_CACHE_ROOT' : str(value) }

def test_cache_root( tmp_path ):
    root = tmp_path / 'scratch'
    proj = _write_proj( tmp_path / 'proj' )
    env = _env( root )
    run( 'sb', proj, env_extra = env )
    cachedir = _expected_cachedir( root, proj, 'myproj' )
    assert sorted( f.name for f in root.iterdir() ) == [ cachedir.name ]
    assert ( cachedir / 'install' ).is_dir() and ( cachedir / 'bld' ).is_dir()
    assert not ( proj / 'simplebuild_cache' ).exists()
    assert ( ( cachedir / 'simplebuild_cfg_path.txt' ).read_text()
             == f'{(proj/"simplebuild.cfg").resolve()}\n' )
    #All commands agree on the location:
    assert ( run( 'sbenv sb_mypkg_hello', proj, env_extra = env ).stdout.strip()
             == 'hello' )
    res = run( [ 'sbenv', 'bash', '-c', 'echo $SBLD_INSTALL_PREFIX' ], proj, env_extra = env )
    assert res.stdout.strip() == str( cachedir / 'install' )
    res = run( 'sb --env-setup', proj, env_extra = env )
    assert str( cachedir / 'install' ) in res.stdout
    #Same location next time (nothing rebuilt), also for other build variants:
    assert n_compiled( run( 'sb', proj, env_extra = env ).out ) == 0
    run( 'sb -d', proj, env_extra = env )
    assert ( cachedir / 'install_debug' ).is_dir()
    #Without the variable, the default location is used:
    run( 'sb', proj )
    assert ( proj / 'simplebuild_cache' / 'install' ).is_dir()
    #Cleaning removes the directory completely:
    run( 'sb -c', proj, env_extra = env )
    assert not cachedir.exists()
    assert root.is_dir() and not any( root.iterdir() )

def test_cache_root_separate_checkouts( tmp_path ):
    root = tmp_path / 'scratch'
    p1 = _write_proj( tmp_path / 'proj1' )
    p2 = _write_proj( tmp_path / 'proj2' )
    p3 = _write_proj( tmp_path / 'unnamed', name = None )
    for p in ( p1, p2, p3 ):
        run( 'sb', p, env_extra = _env( root ) )
    expected = sorted( [ _expected_cachedir( root, p1, 'myproj' ).name,
                         _expected_cachedir( root, p2, 'myproj' ).name,
                         _expected_cachedir( root, p3, 'unnamed' ).name ] )
    assert len( set( expected ) ) == 3
    assert sorted( f.name for f in root.iterdir() ) == expected

def test_cache_root_and_cfg_cachedir( tmp_path ):
    root = tmp_path / 'scratch'
    proj = _write_proj( tmp_path / 'proj',
                        extra_cfg = '[build]\ncachedir = "./mycache"\n' )
    #An explicit cachedir in the cfg file takes precedence:
    run( 'sb', proj, env_extra = _env( root ) )
    assert ( proj / 'mycache' / 'install' ).is_dir()
    assert not root.exists()
    #Unless the "force::" prefix is used:
    run( 'sb', proj, env_extra = _env( f'force::{root}' ) )
    assert ( _expected_cachedir( root, proj, 'myproj' ) / 'install' ).is_dir()

def test_cache_root_errors( tmp_path ):
    root = tmp_path / 'scratch'
    proj = _write_proj( tmp_path / 'proj' )
    for value, msg in [ ( 'relative/path', 'must be set to an absolute path' ),
                        ( 'force::', 'No directory specified after "force::"' ),
                        ( proj / 'simplebuild.cfg', 'does not point to a directory' ),
                        ( f'{tmp_path}/a dir', 'contains unsupported characters' ) ]:
        res = run( 'sb', proj, env_extra = _env( value ), expect_ec = 1 )
        assert msg in res.out, value
        assert 'Traceback' not in res.out
    #A cache directory belonging to another bundle is never used:
    cachedir = _expected_cachedir( root, proj, 'myproj' )
    cachedir.mkdir( parents = True )
    ( cachedir / 'simplebuild_cfg_path.txt' ).write_text( '/some/other/simplebuild.cfg\n' )
    res = run( 'sb', proj, env_extra = _env( root ), expect_ec = 1 )
    assert 'is already used by /some/other/simplebuild.cfg' in res.out
    assert sorted( f.name for f in cachedir.iterdir() ) == [ 'simplebuild_cfg_path.txt' ]
