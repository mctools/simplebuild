import os
import pathlib

import pytest

import sbtestutils

#Settings in the environment of the user which affect the location of the
#cache directories (which the tests rely on) must be ignored. This is done here,
#so it also applies to scripts launched by the tests:
os.environ.pop( 'SIMPLEBUILD_CACHE_ROOT', None )

def pytest_report_header( config ):
    import _simple_build_system
    import shutil
    from sbtestutils import clean_env, required_features
    sb = shutil.which( 'sb', path = clean_env()['PATH'] )
    shells = [ s for s in ('bash','dash','zsh','ksh','ash')
               if shutil.which( s ) ]
    return [ f'simplebuild module: {pathlib.Path(_simple_build_system.__file__).parent}',
             f'sb command: {sb}',
             f'available shells: {" ".join(shells) or "<none>"}',
             f'SBTEST_REQUIRE: {" ".join(sorted(required_features())) or "<none>"}' ]

@pytest.fixture
def make_project( tmp_path ):
    """Factory for creating simplebuild projects in a fresh temporary
    directory. Either run "sb --init" with the given arguments, or write the
    given cfg file content (or both, in which case the content is appended)."""
    def _make( name = 'proj', *, init_args = None, cfg = None ):
        d = tmp_path / name
        d.mkdir()
        if init_args is not None:
            sbtestutils.run( ['sb','--init'] + list(init_args), cwd = d )
        if cfg is not None:
            f = d / 'simplebuild.cfg'
            content = ( f.read_text() if f.exists() else '' ) + cfg
            f.write_text( content )
        return d
    return _make

#Support for classes of tests which must run in order and depend on each other
#(after a failure, the remaining tests are marked as xfail):

def pytest_runtest_makereport( item, call ):
    if 'incremental' in item.keywords and call.excinfo is not None:
        item.parent._previousfailed = item

def pytest_runtest_setup( item ):
    if 'incremental' in item.keywords:
        previousfailed = getattr( item.parent, '_previousfailed', None )
        if previousfailed is not None:
            pytest.xfail( f'previous test failed ({previousfailed.name})' )
