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

def test_testreport( reflogproj ):
    d = reflogproj
    write_files( d, { 'OtherPkg/pkg.info' : 'package()\n',
                      'OtherPkg/scripts/testslow' : '#!/usr/bin/env bash\nsleep 1\n' } )
    ( d / 'OtherPkg' / 'scripts' / 'testslow' ).chmod( 0o755 )
    #No results yet:
    res = run( 'sb --testreport', d, expect_ec = 1 )
    assert 'No test results are available for this build variant' in res.out
    live = run( 'sb -t', d, expect_ec = 73 )
    rows = _result_rows( live.out )
    assert len(rows) == 6
    #Report afterwards is the same:
    res = run( 'sb --testreport', d, expect_ec = 73 )
    assert 'Report of test results from ' in res.out
    assert _result_rows( res.out ) == rows
    assert list( _result_rows( res.out ) ) == sorted( rows )
    assert 'WARNING' not in res.out
    #Sorting:
    res = run( 'sb --testreport=time', d, expect_ec = 73 )
    assert list( _result_rows( res.out ) )[0] == 'sb_otherpkg_testslow'
    res = run( 'sb --testreport=relevance', d, expect_ec = 73 )
    rr = list( _result_rows( res.out ) )
    assert rr == sorted( rr, key = lambda n : ( 'FAIL' not in rows[n], n ) )
    assert 'FAIL' in rows[rr[0]] and 'FAIL' not in rows[rr[-1]]
    res = run( 'sb --testreport=pkg', d, expect_ec = 2 )
    assert 'Invalid keyword "pkg" in --testreport' in res.out
    #Only failed, and filters:
    res = run( 'sb --testreport=failed,name', d, expect_ec = 73 )
    assert sorted( _result_rows( res.out ) ) == sorted( k for k,v in rows.items()
                                                       if 'FAIL' in v )
    assert '(2 of the 6 tests are not shown)' in res.out
    res = run( "sb --testreport --testfilter='*same,*slow'", d )
    assert sorted( _result_rows( res.out ) ) == [ 'sb_mypkg_same', 'sb_otherpkg_testslow' ]
    assert 'All tests completed without failures!' in res.out
    #Also applies when running tests:
    res = run( 'sb -t --testreport=failed', d, expect_ec = 73 )
    assert len( _result_rows( res.out ) ) == 4
    #Results of each build variant are separate:
    res = run( 'sb -d --testreport', d, expect_ec = 1 )
    run( 'sb -d -t --testfilter=sb_mypkg_same', d )
    assert list( _result_rows( run( 'sb -d --testreport', d ).out ) ) == [ 'sb_mypkg_same' ]
    res = run( 'sb --testreport', d, expect_ec = 73 )
    assert _result_rows( res.out ) == rows
    #Warning when the results might be outdated:
    ( d / 'OtherPkg' / 'scripts' / 'testslow' ).write_text( '#!/usr/bin/env bash\n' )
    run( 'sb', d )
    res = run( 'sb --testreport', d, expect_ec = 73 )
    assert 'packages were changed' in res.out and 'OtherPkg' in res.out
    #Invalid usage:
    res = run( 'sb --testreport=bad', d, expect_ec = 2 )
    assert 'Invalid keyword "bad" in --testreport' in res.out
    res = run( 'sb --testreport=time,name', d, expect_ec = 2 )
    assert 'Only one sort order' in res.out
    #--testreport without SPEC has no effect with -t (most likely the intention
    #was to show the previous results, which must be kept):
    before = run( 'sb --testreport', d, expect_ec = 73 ).out
    res = run( 'sb -t --testreport', d, expect_ec = 2 )
    assert '--testreport without SPEC has no effect when running tests' in res.out
    assert run( 'sb --testreport', d, expect_ec = 73 ).out == before
    res = run( 'sb --testreport --pkginfo MyPkg', d, expect_ec = 2 )
    assert 'mutually exclusive' in res.out

def _start_reflogupdate( d, args = () ):
    from sbtestutils import PtyProcess
    p = PtyProcess( [ 'sb', '--reflogupdate', *args ], d )
    p.wait_for_screen( r'Press \? for help' )
    return p

def _confirm_code( p ):
    m = p.wait_for_screen( r'type the code ([a-z0-9]{5}) in reverse order' )
    return m.group(1)

def test_reflogupdate( reflogproj ):
    d = reflogproj
    scripts = d / 'MyPkg' / 'scripts'
    #The reference log in the package might itself be a symlink:
    ( d / 'elsewhere.log' ).write_text( _reflogs['different'] )
    ( scripts / 'different.log' ).unlink()
    ( scripts / 'different.log' ).symlink_to( '../../elsewhere.log' )
    #Non-interactive usage is not possible:
    res = run( 'sb --reflogupdate', d, expect_ec = 1 )
    assert 'requires an interactive terminal' in res.out
    run( 'sb -t', d, expect_ec = 73 )
    p = _start_reflogupdate( d )
    p.wait_for_screen( r'\[1/4\] sb_mypkg_different' )
    #Wrong code:
    p.send( 'u' )
    code = _confirm_code( p )
    p.send( code + '\r' if code != code[::-1] else 'wrong\r' )
    p.wait_for_screen( 'Wrong code, nothing was done' )
    #Right code (moves on to the next test):
    p.send( 'u' )
    p.send( _confirm_code( p )[::-1] + '\r' )
    p.wait_for_screen( r'Updated MyPkg/scripts/different\.log' )
    p.wait_for_screen( r'\[2/4\] sb_mypkg_innerspace' )
    #Disable the code requirement for the rest of the session (also requires
    #a code), and update the remaining ones:
    p.send( 'X' )
    p.send( _confirm_code( p )[::-1] + '\r' )
    p.wait_for_screen( 'Codes are no longer required' )
    p.send( 'u' )
    p.wait_for_screen( r'\[3/4\] sb_mypkg_nonewline' )
    p.send( 'u' )
    p.wait_for_screen( r'\[4/4\] sb_mypkg_trailingspace' )
    p.send( 'u' )
    p.wait_for_screen( 'no more reference logs to update' )
    p.send( 'q' )
    assert p.wait_exit() == 0
    assert 'Updated 4 reference logs:' in p.text
    assert 'MyPkg/scripts/innerspace.log' in p.text
    #The files were updated (also the target of the symlink), without leaving
    #backup files around:
    for name in _reflogs:
        f = scripts / f'{name}.log'
        assert f.read_text() == 'x = 1 2\n', name
    assert ( scripts / 'different.log' ).is_symlink()
    assert ( d / 'elsewhere.log' ).read_text() == 'x = 1 2\n'
    assert sorted( f.name for f in scripts.iterdir() if f.suffix not in ( '', '.log' ) ) == []
    #The test results are updated as well:
    res = run( 'sb --testreport', d )
    assert all( v == ( 'OK', 'OK' ) for v in _result_rows( res.out ).values() )
    res = run( 'sb -t', d )
    assert 'All tests completed without failures!' in res.out
    #Nothing to do now:
    res = run( 'sb --reflogupdate', d, expect_ec = None )
    #(not a terminal, so it fails before we can see that nothing is to be done)
    from sbtestutils import PtyProcess
    p = PtyProcess( [ 'sb', '--reflogupdate' ], d )
    p.wait_for( 'There are no reference logs which differ from the output' )
    assert p.wait_exit() == 0

def test_reflogupdate_rerun_and_rebuild( reflogproj ):
    d = reflogproj
    write_files( d, { 'MyPkg/app_hello/main.cc' : ( '#include <cstdio>\nint main()'
                                                    ' { std::printf("value v1\\n"); return 0; }\n' ),
                      'MyPkg/app_hello/test.log' : 'value v2\n' } )
    p = None
    run( 'sb -t', d, expect_ec = 73 )
    p = _start_reflogupdate( d, [ '--testfilter=*hello,*different' ] )
    p.wait_for_screen( r'\[1/2\] sb_mypkg_different' )
    #Change the script and run the test again:
    ( d / 'MyPkg' / 'scripts' / 'different' ).write_text( '#!/usr/bin/env bash\necho "x = 1 3"\n' )
    p.send( 'r' )
    p.wait_for_screen( 'The output is now identical to the reference log' )
    #Change the C++ code, rebuild, and run the test again:
    p.send( '+' )
    p.wait_for_screen( r'\[2/2\] sb_mypkg_hello' )
    ( d / 'MyPkg' / 'app_hello' / 'main.cc' ).write_text(
        '#include <cstdio>\nint main() { std::printf("value v2\\n"); return 0; }\n' )
    p.send( 'b' )
    p.wait_for( 'Rebuilding before running sb_mypkg_hello again' )
    p.wait_for_screen( r'hello.*IDENTICAL', timeout = 300 )
    p.send( 'q' )
    assert p.wait_exit() == 0
    assert 'Updated 0 reference logs.' in p.text
    assert not ( d / 'simplebuild_cache' / 'bld' / '.lock' ).exists()
    rows = _result_rows( run( "sb --testreport --testfilter='*hello,*different'", d ).out )
    assert rows == { 'sb_mypkg_different' : ( 'OK', 'OK' ),
                     'sb_mypkg_hello' : ( 'OK', 'OK' ) }

def test_old_reflogupdate_command( reflogproj ):
    d = reflogproj
    run( 'sb', d )
    res = run( 'sbenv sb_core_reflogupdate', d, expect_ec = 1 )
    assert 'replaced by the --reflogupdate\noption of sb' in res.out

def test_slowest_tests_started_first( tmp_path ):
    import json
    d = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
              'MyPkg/pkg.info' : 'package()\n',
              'MyPkg/scripts/testa_fast' : '#!/usr/bin/env bash\n',
              'MyPkg/scripts/testm_medium' : '#!/usr/bin/env bash\nsleep 0.3\n',
              'MyPkg/scripts/testz_slow' : '#!/usr/bin/env bash\nsleep 1\n' }
    write_files( d, files )
    for f in ( d / 'MyPkg' / 'scripts' ).iterdir():
        f.chmod( 0o755 )
    def started_order():
        mf = ( _testdir(d) / 'Makefile' ).read_text()
        line = next( line for line in mf.splitlines() if line.startswith('all:') )
        return [ e.split('_',2)[2] for e in line.split()[1:] ]
    #No timings at first:
    run( 'sb -t', d )
    assert started_order() == [ 'testa_fast', 'testm_medium', 'testz_slow' ]
    timings = json.loads( ( d / 'simplebuild_cache' / 'bld' / 'testtimings.json' ).read_text() )
    assert sorted( timings ) == [ 'sb_mypkg_testa_fast', 'sb_mypkg_testm_medium',
                                  'sb_mypkg_testz_slow' ]
    assert timings['sb_mypkg_testz_slow'] >= 1000.0
    run( 'sb -t', d )
    assert started_order() == [ 'testz_slow', 'testm_medium', 'testa_fast' ]
    #New tests (without timings) are started first, and timings of tests not
    #run are kept:
    write_files( d, { 'MyPkg/scripts/testb_new' : '#!/usr/bin/env bash\n' } )
    ( d / 'MyPkg' / 'scripts' / 'testb_new' ).chmod( 0o755 )
    run( "sb -t --testfilter='!*medium'", d )
    assert started_order() == [ 'testb_new', 'testz_slow', 'testa_fast' ]
    run( 'sb -t', d )
    assert started_order() == [ 'testz_slow', 'testm_medium', 'testa_fast', 'testb_new' ] or \
        started_order() == [ 'testz_slow', 'testm_medium', 'testb_new', 'testa_fast' ]

def test_interactive_testreport( reflogproj ):
    from sbtestutils import PtyProcess
    d = reflogproj
    write_files( d, { 'MyPkg/scripts/testfails' :
                      '#!/usr/bin/env bash\necho "this test fails"\nexit 3\n' } )
    ( d / 'MyPkg' / 'scripts' / 'testfails' ).chmod( 0o755 )
    #Non-interactive usage is not possible:
    res = run( 'sb --testreport=interactive', d, expect_ec = 1 )
    assert 'requires an interactive terminal' in res.out
    run( 'sb -t', d, expect_ec = 73 )
    p = PtyProcess( [ 'sb', '--testreport=interactive',
                      "--testfilter=*testfails,*same,*innerspace" ], d )
    p.wait_for_screen( r'Press \? for help' )
    p.wait_for_screen( r'sb --testreport +3 tests, 2 failed +sort: relevance' )
    assert 'sb_mypkg_trailingspace' not in p.screen()
    #Failed tests first by default:
    rows = [ line.split()[0] for line in p.screen().splitlines() if line.startswith('  sb_') ]
    assert rows == [ 'sb_mypkg_innerspace', 'sb_mypkg_testfails', 'sb_mypkg_same' ]
    #Only failed tests:
    p.send( 'f' )
    p.wait_for_screen( r'only failed tests shown' )
    rows = [ line.split()[0] for line in p.screen().splitlines() if line.startswith('  sb_') ]
    assert rows == [ 'sb_mypkg_innerspace', 'sb_mypkg_testfails' ]
    #Output of the failed test:
    p.send( 'j' )
    p.send( '\r' )
    p.wait_for_screen( r'Output of sb_mypkg_testfails \(exit code 3\)' )
    p.wait_for_screen( r'1 this test fails' )
    p.send( '\x1b' )#Esc: back
    #Differences with the reference log, and update of the reference log:
    p.send( 'k' )
    p.send( '\r' )
    p.wait_for_screen( r'sb --testreport +\[1/1\] sb_mypkg_innerspace' )
    p.send( 'u' )
    m = p.wait_for_screen( r'type the code ([a-z0-9]{5}) in reverse order' )
    p.send( m.group(1)[::-1] + '\r' )
    p.wait_for_screen( 'Updated MyPkg/scripts/innerspace.log' )
    p.send( '\x1b' )#Esc: back
    p.wait_for_screen( r'3 tests, 1 failed' )
    #Fix the failing test and run it again:
    ( d / 'MyPkg' / 'scripts' / 'testfails' ).write_text( '#!/usr/bin/env bash\necho fixed\n' )
    p.send( 'r' )
    p.wait_for_screen( 'sb_mypkg_testfails now passes' )
    p.wait_for_screen( r'3 tests, 0 failed' )
    #Sort order:
    p.send( 'F' )
    p.send( 's' )
    p.wait_for_screen( r'sort: time' )
    p.send( 's' )
    p.wait_for_screen( r'sort: name' )
    #Esc (back) does not quit the top level screen:
    p.send( '\x1b' )
    p.wait_for_screen( r'Press q to quit' )
    p.send( 'Q' )
    assert p.wait_exit() == 0
    #The usual report follows, and reflects the changes:
    assert 'Updated 1 reference log:' in p.text
    assert 'All tests completed without failures!' in p.text
    assert ( d / 'MyPkg' / 'scripts' / 'innerspace.log' ).read_text() == 'x = 1 2\n'
    rows = _result_rows( run( "sb --testreport --testfilter=*testfails,*innerspace", d ).out )
    assert rows == { 'sb_mypkg_innerspace' : ( 'OK', 'OK' ),
                     'sb_mypkg_testfails' : ( 'OK', '--' ) }

def test_rerun_from_output_view( reflogproj ):
    #Tests can be run again from the view of their output, with the output
    #appearing while the test runs:
    from sbtestutils import PtyProcess
    d = reflogproj
    script = d / 'MyPkg' / 'scripts' / 'testfails'
    write_files( d, { 'MyPkg/scripts/testfails' :
                      '#!/usr/bin/env bash\necho "this test fails"\nexit 3\n' } )
    script.chmod( 0o755 )
    run( 'sb -t', d, expect_ec = 73 )
    p = PtyProcess( [ 'sb', '--testreport=interactive,failed',
                      '--testfilter=*testfails' ], d )
    p.wait_for_screen( r'Press \? for help' )
    p.send( '\r' )
    p.wait_for_screen( r'Output of sb_mypkg_testfails \(exit code 3\)' )
    p.wait_for_screen( r'1 this test fails' )
    script.write_text( '#!/usr/bin/env bash\necho "first part"\nsleep 3\n'
                       'echo "second part"\n' )
    p.send( 'r' )
    p.wait_for_screen( r'Output of sb_mypkg_testfails \(running\.\.\.\)' )
    screen = p.wait_for_screen( r'1 first part' ).string
    assert 'second part' not in screen
    p.wait_for_screen( r'2 second part', timeout = 60 )
    p.wait_for_screen( r'sb_mypkg_testfails now passes' )
    p.wait_for_screen( r'Output of sb_mypkg_testfails \(exit code 0\)' )
    #Back in the table, the result is updated:
    p.send( '\x1b' )
    p.wait_for_screen( r'1 tests, 0 failed' )
    p.send( 'q' )
    assert p.wait_exit() == 0

def test_interactive_testreport_with_tests( reflogproj ):
    from sbtestutils import PtyProcess
    d = reflogproj
    p = PtyProcess( [ 'sb', '-t', '--testreport=interactive,failed',
                      '--testfilter=*same,*different' ], d )
    p.wait_for_screen( r'sb --testreport +2 tests, 1 failed', timeout = 300 )
    rows = [ line.split()[0] for line in p.screen().splitlines() if line.startswith('  sb_') ]
    assert rows == [ 'sb_mypkg_different' ]
    p.send( 'q' )
    assert p.wait_exit() == 73
    assert 'ERROR: Some tests failed!' in p.text

def test_interactive_rebuild_failure_shows_build_log( reflogproj ):
    #When a rebuild from the interactive interfaces fails, the output of the
    #build (e.g. compilation errors) is shown, and can be shown again later:
    from sbtestutils import PtyProcess
    d = reflogproj
    write_files( d, { 'MyPkg/app_hello/main.cc' : ( '#include <cstdio>\nint main()'
                                                    ' { std::printf("value v1\\n"); return 0; }\n' ),
                      'MyPkg/app_hello/test.log' : 'value v2\n' } )
    run( 'sb -t', d, expect_ec = 73 )
    p = PtyProcess( [ 'sb', '--testreport=interactive', '--testfilter=*hello' ], d )
    p.wait_for_screen( r'sb --testreport +1 tests, 1 failed' )
    #Introduce a compilation error, and rebuild+rerun:
    ( d / 'MyPkg' / 'app_hello' / 'main.cc' ).write_text( 'int main() { this_is_an_error; }\n' )
    p.send( 'b' )
    p.wait_for_screen( r'The build FAILED\. Output of the build:', timeout = 300 )
    p.wait_for_screen( r'this_is_an_error' )
    p.send( '\x1b' )#Esc: back
    p.wait_for_screen( r'Build failed' )
    #Show it again:
    p.send( 'e' )
    p.wait_for_screen( r'Output of the last build:' )
    p.wait_for_screen( r'this_is_an_error' )
    p.send( '\x1b' )#Esc: back
    #Also from the reference log viewer:
    p.send( '\r' )
    p.wait_for_screen( r'\[1/1\] sb_mypkg_hello' )
    p.send( 'E' )
    p.wait_for_screen( r'Output of the last build:' )
    p.send( '\x1b' )#Esc: back to the reference log viewer
    p.wait_for_screen( r'sb --testreport.*sb_mypkg_hello' )
    #q quits directly, also from screens opened from other screens:
    p.send( 'q' )
    assert p.wait_exit() == 73

@pytest.fixture
def slowproj( tmp_path ):
    d = tmp_path / 'proj'
    files = { 'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
              'LivePkg/pkg.info' : 'package()\n',
              'LivePkg/scripts/testbad' : '#!/usr/bin/env bash\necho bad\nexit 2\n' }
    for i in range(1,5):
        files[f'LivePkg/scripts/testslow{i}'] = f'#!/usr/bin/env bash\nsleep {i}\necho t{i}\n'
    write_files( d, files )
    for f in ( d / 'LivePkg' / 'scripts' ).iterdir():
        f.chmod( 0o755 )
    return d

def test_testtime( slowproj ):
    #With --testtime, only the shortest tests (according to previous timings)
    #which fit within the given time are run, as well as any tests without
    #previous timings:
    d = slowproj
    run( 'sb -t -j1', d, expect_ec = 73 )#record timings
    write_files( d, { 'LivePkg/scripts/testnew' : '#!/usr/bin/env bash\necho new\n' } )
    ( d / 'LivePkg' / 'scripts' / 'testnew' ).chmod( 0o755 )
    res = run( 'sb -t -j1 --testtime=4.5', d, expect_ec = 73 )
    expected = [ 'sb_livepkg_testbad', 'sb_livepkg_testnew',
                 'sb_livepkg_testslow1', 'sb_livepkg_testslow2' ]
    assert sorted( _result_rows( res.out ) ) == expected
    note = 'Note: 2 tests were not run due to --testtime=4.5 (they took 7s in total in previous runs).'
    assert note in res.out
    #Also noted in later reports:
    res = run( 'sb --testreport', d, expect_ec = 73 )
    assert note in res.out and sorted( _result_rows( res.out ) ) == expected
    #Invalid usage:
    res = run( 'sb --testtime=10', d, expect_ec = 2 )
    assert '--testtime can only be used when running tests' in res.out
    res = run( 'sb -t --testtime=0', d, expect_ec = 2 )
    assert '--testtime requires a positive number of seconds' in res.out

def test_progress_line_and_interactive_view( slowproj ):
    #When running tests in a terminal, the progress is shown (including an
    #estimate of the remaining time, once timings from previous runs are
    #available), and "i" opens the interactive view while tests continue:
    from sbtestutils import PtyProcess
    d = slowproj
    p = PtyProcess( [ 'sb', '-t', '-j2' ], d )
    p.wait_for( r'sbld:  Tests done: \d/5[^\r\n]*\[press i for interactive view\]', timeout = 300 )
    p.wait_for( r'Tests done: 5/5, 1 failed' )
    assert p.wait_exit() == 73
    assert 'ERROR: Some tests failed!' in p.text
    #Now with timings from the previous run:
    p = PtyProcess( [ 'sb', '-t', '-j2' ], d )
    p.wait_for( r'Tests done: \d/5[^\r\n]*~\d+s left', timeout = 300 )
    p.send( 'I' )
    p.wait_for_screen( r'running tests: \d/5 done, ~\d+s left' )
    p.wait_for_screen( r'Tests are running in the background' )
    p.wait_for_screen( r'(RUNNING|WAITING)' )
    p.wait_for_screen( r'All tests finished', timeout = 60 )
    p.wait_for_screen( r'5 tests, 1 failed' )
    p.send( 'q' )
    assert p.wait_exit() == 73
    rows = _result_rows( p.text.split('Tests done: 5/5')[-1] )
    assert len( rows ) == 5 and rows['sb_livepkg_testbad'] == ( 'FAIL', '--' )

def test_interactive_live_results( slowproj ):
    from sbtestutils import PtyProcess
    d = slowproj
    p = PtyProcess( [ 'sb', '-t', '-j2', '--testreport=interactive' ], d )
    p.wait_for_screen( r'running tests: \d/5 done', timeout = 300 )
    p.wait_for_screen( r'All tests finished', timeout = 60 )
    p.wait_for_screen( r'5 tests, 1 failed' )
    #Run the shown tests again in the background, and cancel them:
    p.send( 't' )
    p.wait_for_screen( r'Running 5 tests in the background' )
    p.wait_for_screen( r'running tests: \d/5 done, ~\d+s left' )
    p.send( 'c' )
    p.wait_for_screen( r'The tests were cancelled' )
    p.send( 'q' )
    assert p.wait_exit() == 73
    assert 'ERROR: Some tests failed!' in p.text
    #Cancelled tests are reported as failed:
    res = run( 'sb --testreport=failed', d, expect_ec = 73 )
    assert len( _result_rows( res.out ) ) >= 2
    #Running everything again (non-interactively, so without progress line):
    res = run( 'sb -t', d, expect_ec = 73 )
    assert 'Tests done:' not in res.out
    assert len( [ v for v in _result_rows( res.out ).values() if v[0] == 'FAIL' ] ) == 1

def test_fastest_first_and_inspecting_during_run( slowproj ):
    #The output of finished tests (failed or not) can be inspected while other
    #tests are still running, and --testorder=fastest starts the fastest tests
    #first (to get results quickly):
    from sbtestutils import PtyProcess
    d = slowproj
    run( 'sb -t', d, expect_ec = 73 )#record timings
    def started_order():
        mf = ( _testdir(d) / 'Makefile' ).read_text()
        line = next( line for line in mf.splitlines() if line.startswith('all:') )
        return [ e.split('_',2)[2] for e in line.split()[1:] ]
    run( 'sb -t --testorder=fastest', d, expect_ec = 73 )
    assert started_order() == [ 'testbad', 'testslow1', 'testslow2',
                                'testslow3', 'testslow4' ]
    p = PtyProcess( [ 'sb', '-t', '-j1', '--testreport=interactive,name',
                      '--testorder=fastest' ], d )
    #testbad and testslow1 finish first, while testslow4 is still waiting:
    p.wait_for_screen( r'running tests: [2-4]/5 done', timeout = 300 )
    screen = p.screen()
    assert 'WAITING' in screen.split('sb_livepkg_testslow4')[1].splitlines()[0]
    #Output of a failed test (the first row):
    p.send( '\r' )
    p.wait_for_screen( r'Output of sb_livepkg_testbad \(exit code 2\)' )
    p.wait_for_screen( r'1 bad' )
    p.send( '\x1b' )#Esc: back
    #Output of a successful test:
    p.send( 'j' )
    p.send( 'o' )
    p.wait_for_screen( r'Output of sb_livepkg_testslow1' )
    p.wait_for_screen( r'1 t1' )
    p.send( '\x1b' )#Esc: back
    p.wait_for_screen( r'All tests finished', timeout = 60 )
    p.send( 'q' )
    assert p.wait_exit() == 73
