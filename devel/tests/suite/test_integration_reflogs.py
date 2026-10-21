# Tests with reference logs: comparison of the output, reporting of the
# results, and updating of the reference logs.

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

#Test scripts and their reference logs (output of all scripts is "x = 1 2"):
_reflogs = {
    'same' : 'x = 1 2\n',
    'trailingspace' : 'x = 1 2  \n',
    'innerspace' : 'x = 12\n',
    'nonewline' : 'x = 1 2',
    'different' : 'x = 1 3\n',
}

def _testdir( d ):
    return d / 'simplebuild_cache' / 'bld' / 'testresults'

def _result_rows( out ):
    """Parse the rows of the test result table into dict of
    name->(ec,logdiff)."""
    import re
    res = {}
    for line in out.splitlines():
        line = re.sub( r'^sbld:', '', line )
        parts = [ e.strip() for e in line.split('|') ]
        if len(parts) == 5 and parts[0].startswith('sb_'):
            res[parts[0]] = ( parts[2], parts[3] )
    return res

@pytest.fixture
def reflogproj( tmp_path ):
    d = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
              'MyPkg/pkg.info' : 'package()\n' }
    for name, reflog in _reflogs.items():
        files[f'MyPkg/scripts/{name}'] = '#!/usr/bin/env bash\necho "x = 1 2"\n'
        files[f'MyPkg/scripts/{name}.log'] = reflog
    write_files( d, files )
    for name in _reflogs:
        ( d / 'MyPkg' / 'scripts' / name ).chmod( 0o755 )
    return d

def test_exact_comparison( reflogproj ):
    d = reflogproj
    res = run( 'sb -t', d, expect_ec = 73 )
    rows = _result_rows( res.out )
    assert rows['sb_mypkg_same'] == ( 'OK', 'OK' )
    for name in _reflogs:
        if name != 'same':
            assert rows[f'sb_mypkg_{name}'] == ( 'OK', 'FAIL' ), name
            diff = ( _testdir(d) / f'sb_mypkg_{name}' / 'refdiff.log' ).read_text()
            assert ( diff.startswith( 'NOTE: The output differs from the'
                                      ' reference log only in whitespace' )
                     == ( name != 'different' ) ), name
