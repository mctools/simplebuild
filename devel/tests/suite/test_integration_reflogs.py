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

def test_excerpts( reflogproj ):
    d = reflogproj
    write_files( d, { 'MyPkg/scripts/testfails' :
                      '#!/usr/bin/env bash\nfor i in $(seq 1 30); do echo "line $i"; done\nexit 1\n' } )
    ( d / 'MyPkg' / 'scripts' / 'testfails' ).chmod( 0o755 )
    res = run( 'sb -t --testexcerpts=3', d, expect_ec = 73 )
    out = res.out
    #Differences, with changed words marked (no colours since the output is
    #not a terminal):
    assert 'All 4 lines of differences between reference log and output of sb_mypkg_innerspace' in out
    assert '-x = [-12-]\n+x = {+1 2+}\n' in out
    assert ( 'NOTE: The output differs from the reference log only in whitespace'
             in out.split('sb_mypkg_innerspace:')[1] )
    assert '-x = 1 [-3-]\n+x = 1 {+2+}\n' in out
    #Output of a failed test is shortened:
    assert 'First 3 lines of output of sb_mypkg_testfails' in out
    assert 'line 1\nline 2\nline 3\n' in out
    assert '(24 lines omitted)' in out
    assert 'line 28\nline 29\nline 30\n' in out
    assert 'line 4\n' not in out
