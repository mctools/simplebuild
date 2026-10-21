# Build variants (extra flags, -d/-r/-g/-x, cache dir management). The test
# logic lives in the standalone script devel/tests/test_build_variants.py,
# which is also invoked directly (outside pytest) by the test-build-variants
# workflow. Here we run each of its phases as separate tests.

import importlib.util

import pytest

from sbtestutils import clean_env, devel_tests_dir

pytestmark = pytest.mark.integration

@pytest.fixture( scope = 'module' )
def bvmod( tmp_path_factory ):
    f = devel_tests_dir / 'test_build_variants.py'
    spec = importlib.util.spec_from_file_location( 'sbtest_build_variants', f )
    mod = importlib.util.module_from_spec( spec )
    spec.loader.exec_module( mod )
    mod.workdir = tmp_path_factory.mktemp( 'bv' ) / 'sbtest_build_variants'
    mod.cachedir = mod.workdir / 'simplebuild_cache'
    #The script uses commands from the PATH:
    mp = pytest.MonkeyPatch()
    mp.setenv( 'PATH', clean_env()['PATH'] )
    mod.setup_project()
    yield mod
    mp.undo()

@pytest.mark.incremental
class TestBuildVariants:

    def test_cfg_validation( self, bvmod ):
        bvmod.test_cfg_validation()

    def test_flag_parsing_equivalence( self, bvmod ):
        bvmod.test_flag_parsing_equivalence()

    def test_variants( self, bvmod ):
        bvmod.test_variants()

    def test_launchers( self, bvmod ):
        bvmod.test_launchers()

    def test_determinism( self, bvmod ):
        bvmod.test_determinism()

    def test_env_setup( self, bvmod ):
        bvmod.test_env_setup()

    def test_max_cachedirs( self, bvmod ):
        bvmod.test_max_cachedirs()

def test_all_phases_covered( bvmod ):
    #Make sure we do not forget to add phases added to the standalone script:
    phases = sorted( n for n in dir(bvmod) if n.startswith('test_') )
    covered = sorted( n for n in dir(TestBuildVariants) if n.startswith('test_') )
    assert phases == covered
