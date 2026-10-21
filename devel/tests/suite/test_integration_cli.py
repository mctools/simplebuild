import pytest

from sbtestutils import run

pytestmark = pytest.mark.integration

def test_version( tmp_path ):
    import _simple_build_system._determine_version as dv
    res = run( 'sb --version', tmp_path )
    assert res.stdout.strip() == dv.determine_version()

@pytest.mark.parametrize( 'cmd, expected', [
    ( 'sb --help', 'Selecting the build variant:' ),
    ( 'sb --init --help', 'New bundle initialisation mode' ),
    ( 'sbenv --help', 'usage: sbenv [-h] [-d|-r|-g] [-x] <program> [args]' ),
    ( 'sbrun --help', 'usage: sbrun [-h] [-d|-r|-g] [-x] <program> [args]' ),
] )
def test_help( tmp_path, cmd, expected ):
    assert expected in run( cmd, tmp_path ).stdout

def test_outside_project( tmp_path ):
    res = run( 'sb', tmp_path, expect_ec = 1 )
    assert 'please step into a directory tree with a simplebuild.cfg' in res.out
    #--env-unsetup works also outside projects:
    run( 'sb --env-unsetup', tmp_path )
    #As does the hidden flag used by the shell snippet (silently):
    res = run( 'unwrapped_simplebuild --env-setup-after-build', tmp_path )
    assert not res.stdout and not res.stderr

def test_simplebuild_cfg_env_var( make_project, tmp_path ):
    d = make_project( cfg = '[bundle]\nname = "proj"\n' )
    other = tmp_path / 'elsewhere'
    other.mkdir()
    res = run( 'sb --env-setup', other,
               env_extra = { 'SIMPLEBUILD_CFG' : str(d / 'simplebuild.cfg') } )
    assert str( d / 'simplebuild_cache' / 'install' ) in res.stdout
