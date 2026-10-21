# Tests of the sb shell function (shellrc_snippet.sh) and environment setup in
# various shells. These run the same shell scripts which are also invoked
# directly (outside pytest) by devel/tests/test_envsetup_manyshells.x in the
# testshells workflow.

import shutil

import pytest

from sbtestutils import devel_tests_dir, reporoot, require_feature, run

pytestmark = pytest.mark.shells

#important shells:
#  ksh (openbsd)
#  zsh (osx)
#  dash (ubuntu)
#  bash4 (most other modern linux)
#  bash3 (osx for people who switched to bash)
#  ash (??)
@pytest.mark.parametrize( 'shell', [ 'bash', 'dash', 'zsh', 'ksh', 'ash' ] )
def test_envsetup( tmp_path, shell ):
    shell_path = shutil.which( shell )
    require_feature( f'shell:{shell}', shell_path is not None,
                     f'{shell} not found' )
    resdir = reporoot / 'resources'
    env = { 'SBTEST_SHELLSNIPPET' : str( resdir / 'shellrc_snippet.sh' ),
            'SBTEST_SHELLSNIPPET_DEACTIVATE' : str( resdir / 'shellrc_snippet_deactivate.sh' ),
            'SBTEST_OLD_SHELLSNIPPET' : str( devel_tests_dir / 'old_shellrc_snippet.sh' ),
            'SBTEST_ALLOW_VAR_LEAK' : '1' if shell == 'ksh' else '0',
            'SBTEST_HAS_TYPESETMINUSF' : '0' if shell in ('dash','ash') else '1',
            'SHELL' : shell_path }
    res = run( [ shell_path, devel_tests_dir / 'test_envsetup.sh' ], tmp_path,
               env_extra = env )
    assert res.stdout.rstrip().endswith( 'All good' )

def test_sbswitch( tmp_path ):
    require_feature( 'shell:bash', shutil.which('bash') is not None,
                     'bash not found' )
    res = run( [ devel_tests_dir / 'test_sbswitch.x' ], tmp_path )
    assert 'ALL OK' in res.out
