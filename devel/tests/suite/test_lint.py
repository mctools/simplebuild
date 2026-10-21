import shutil

import pytest

from sbtestutils import ( have_cmd, reporoot, require_feature,
                          require_test_dependency, run )

pytestmark = pytest.mark.unit

def test_ruff( tmp_path ):
    require_test_dependency( 'ruff', have_cmd('ruff') )
    require_feature( 'shell:bash', shutil.which('bash') is not None,
                     'bash not found' )
    run( [ reporoot / 'devel' / 'ruff.x' ], tmp_path )
