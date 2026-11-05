# Tests of sb -t --failearly (issue #68), which stops the tests as soon as one
# of them fails.

import time
import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\n  name = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/testok' : '#!/usr/bin/env bash\necho ok\n',
        'MyPkg/scripts/testslow' : '#!/usr/bin/env bash\nsleep 30\n',
        'MyPkg/scripts/testlog' : '#!/usr/bin/env bash\necho hello\n',
        'MyPkg/scripts/testlog.log' : 'hello\n',
    } )
    for f in ( d / 'MyPkg' / 'scripts' ).iterdir():
        if not f.name.endswith( '.log' ):
            f.chmod( 0o755 )
    return d

def _rows( out ):
    #The rows of the table of test results, as name -> list of columns:
    res = {}
    for line in out.splitlines():
        cols = [ e.strip() for e in line.replace( 'sbld:', '' ).split( '|' ) ]
        if len( cols ) == 5 and cols[0].startswith( 'sb_mypkg_' ):
            res[cols[0]] = cols[1:]
    return res

def _failing_test( d, script ):
    p = d / 'MyPkg' / 'scripts' / 'testfail'
    p.write_text( script )
    p.chmod( 0o755 )

def test_failearly( proj ):
    d = proj
    _failing_test( d, '#!/usr/bin/env bash\nexit 1\n' )
    run( 'sb', d )
    t0 = time.time()
    res = run( 'sb -t --failearly -j2', d, expect_ec = 73 )
    assert time.time() - t0 < 25.0
    rows = _rows( res.out )
    assert rows['sb_mypkg_testfail'][1] == 'FAIL'
    assert rows['sb_mypkg_testslow'][1:] == [ '--', '--', 'Aborted due to --failearly' ]
    assert 'aborted or not started, since another test failed (--failearly)' in res.out
    assert 'Some tests failed' in res.out
    xml = ( d / 'simplebuild_cache' / 'bld' / 'testresults'
            / 'simplebuild_test_results_junitformat.xml' ).read_text()
    #(which tests besides testslow were aborted depends on the timing):
    naborted = sum( 1 for r in rows.values() if r[3] == 'Aborted due to --failearly' )
    assert 'failures="1"' in xml and f'skipped="{naborted}"' in xml
    assert '<skipped message="Aborted due to --failearly" />' in xml
    #The post-factum report shows the same:
    res = run( 'sb --testreport', d, expect_ec = 73 )
    assert _rows( res.out )['sb_mypkg_testslow'][3] == 'Aborted due to --failearly'

def test_failearly_reflog( proj ):
    #Differences with reference logs also count as failures:
    d = proj
    ( d / 'MyPkg' / 'scripts' / 'testlog.log' ).write_text( 'goodbye\n' )
    run( 'sb', d )
    t0 = time.time()
    res = run( 'sb -t --failearly -j2', d, expect_ec = 73 )
    assert time.time() - t0 < 25.0
    rows = _rows( res.out )
    assert rows['sb_mypkg_testlog'][2] == 'FAIL'
    assert rows['sb_mypkg_testslow'][3] == 'Aborted due to --failearly'

def test_failearly_without_failures( proj ):
    d = proj
    ( d / 'MyPkg' / 'scripts' / 'testslow' ).write_text( '#!/usr/bin/env bash\nsleep 1\n' )
    res = run( 'sb -t --failearly', d )
    assert 'aborted' not in res.out.lower()
    assert 'All tests completed without failures' in res.out

def test_failearly_requires_tests( proj ):
    res = run( 'sb --failearly', proj, expect_ec = 2 )
    assert '--failearly can only be used when running tests (-t)' in res.stderr
