# Building and testing the core_val bundle in various ways. This repeats tests
# originally carried out directly in the basictest and condatest workflows.

import os

import pytest

from sbtestutils import ( expected_disabled_extdeps, have_cmd,
                          require_feature, run, run_bash, summary_line )

pytestmark = pytest.mark.integration

def check_extdeps( projdir ):
    disabled = expected_disabled_extdeps()
    cmd = [ 'sbenv', 'sb_core_extdeps' ]
    if disabled:
        cmd += [ '--require-disabled' ] + disabled
    run( cmd, projdir )

def check_env_setup( projdir ):
    #Verify that eval "$(sb --env-setup)" works:
    run_bash( 'eval "$(sb --env-setup)"\n'
              'python3 -c "import _simple_build_system.envsetup as sbe;'
              ' sbe.verify_env_already_setup()"', projdir )

@pytest.mark.parametrize( 'init_args, mode', [
    ( [ 'core_val' ], 'release' ),
    ( [ 'core_val', 'DEBUG', 'COMPACT' ], 'debug' ),
    ( [ 'core_val', 'RELDBG', 'COMPACT' ], 'reldbg' ),
] )
def test_coreval( make_project, init_args, mode ):
    d = make_project( init_args = init_args )
    res = run( 'sb -t --testexcerpts=100 --requirepkg CoreTests', d )
    assert summary_line( res.out, 'Build mode' ) == mode
    assert 'All tests completed without failures!' in res.out
    check_extdeps( d )
    if mode == 'release':
        res = run( "sb -t --testfilter=sb_coretests_testpycpp"
                   " --requirepkg CoreTests", d )
        assert 'sb_coretests_testpycpp' in res.out
        assert 'sb_coretests_testfile' not in res.out
    check_env_setup( d )
    #Clean up all cache directories (incl. the default cache dir):
    run( 'sb -c', d )
    assert not ( d / 'simplebuild_cache' ).exists()

@pytest.fixture( scope = 'module' )
def coreval_custom_cachedir( tmp_path_factory ):
    d = tmp_path_factory.mktemp('coreval_custom_cachedir')
    run( 'sb --init core_val RELEASE COMPACT CACHEDIR::./somecustomcachedir', d )
    run( 'sb -t --testexcerpts=100 --requirepkg CoreTests', d )
    return d

def test_custom_cachedir( coreval_custom_cachedir ):
    d = coreval_custom_cachedir
    assert ( d / 'somecustomcachedir' / 'install' ).is_dir()
    assert not ( d / 'simplebuild_cache' ).exists()
    check_extdeps( d )
    run( "sb -t --testfilter=sb_coretests_testpycpp --requirepkg CoreTests", d )

def test_ncrystal_linkage( coreval_custom_cachedir ):
    require_feature( 'ncrystal', have_cmd('ncrystal-config'),
                     'ncrystal-config command not found' )
    run( "sb -t --testexcerpts=100 --requirepkg 'CoreTests,CoreLinkTests'",
         coreval_custom_cachedir )

def test_cppcheck( coreval_custom_cachedir ):
    require_feature( 'ncrystal', have_cmd('ncrystal-config'),
                     'ncrystal-config command not found' )
    require_feature( 'cppcheck', have_cmd('cppcheck'),
                     'cppcheck command not found' )
    d = coreval_custom_cachedir
    run( "sb --exportcmds=cmds.json --requirepkg 'CoreTests,CoreLinkTests'", d )
    assert ( d / 'cmds.json' ).is_file()
    ( d / 'cppcheck_cache' ).mkdir()
    cmd = [ 'cppcheck', '--inline-suppr', '--project=cmds.json',
            '--check-level=exhaustive', '-j4',
            f'--cppcheck-build-dir={d}/cppcheck_cache', '--error-exitcode=1' ]
    if os.environ.get('CONDA_PREFIX'):
        cmd.append( '--suppress=*:%s/include/*'%os.environ['CONDA_PREFIX'] )
    run( cmd, d )
