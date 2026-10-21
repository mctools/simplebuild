import shutil

import pytest

from sbtestutils import have_cmd, reporoot, require_feature, run

pytestmark = pytest.mark.unit

def test_ruff( tmp_path ):
    require_feature( 'ruff', have_cmd('ruff'), 'ruff command not found' )
    require_feature( 'shell:bash', shutil.which('bash') is not None,
                     'bash not found' )
    run( [ reporoot / 'devel' / 'ruff.x' ], tmp_path )
