import os
import time

from _simple_build_system import testlauncher

def _fake_run( testdir, timings, njobs = 2 ):
    #A BackgroundTestRun object without an actual run (the status of each test
    #is determined from files in testdir):
    run = object.__new__( testlauncher.BackgroundTestRun )
    run.testdir = testdir
    run.njobs = njobs
    run.timings = timings
    run.names = sorted( timings ) + [ 'notiming' ]
    run._finished = False
    return run

def _start( testdir, name, seconds_ago ):
    f = testdir / name / 'time_start'
    f.parent.mkdir( parents = True, exist_ok = True )
    f.touch()
    t = time.time() - seconds_ago
    os.utime( f, ( t, t ) )

def _finish( testdir, name ):
    ( testdir / name / 'ec.txt' ).write_text( '0\n' )

def test_time_remaining( tmp_path ):
    run = _fake_run( tmp_path, { 'a' : 10000.0, 'b' : 4000.0, 'c' : 2000.0 } )
    #Nothing started (longest test vs. total work divided by njobs):
    eta, nunknown = run.time_remaining()
    assert nunknown == 1 and abs( eta - 10.0 ) < 0.1
    #a has been running for 7s:
    _start( tmp_path, 'a', 7.0 )
    eta, nunknown = run.time_remaining()
    assert abs( eta - 4.5 ) < 0.5
    #a, b and c done:
    for n in 'abc':
        _start( tmp_path, n, 1.0 )
        _finish( tmp_path, n )
    assert run.time_remaining() == ( None, 1 )

def test_time_remaining_unknown_when_overrunning( tmp_path ):
    #A test running for longer than in previous runs has an unknown remaining
    #time (rather than 0s):
    run = _fake_run( tmp_path, { 'a' : 2000.0, 'b' : 1000.0 } )
    _start( tmp_path, 'a', 5.0 )
    _start( tmp_path, 'b', 0.0 )
    eta, nunknown = run.time_remaining()
    assert eta is not None and abs( eta - 1.0 ) < 0.2
    _start( tmp_path, 'b', 3.0 )
    assert run.time_remaining() == ( None, 1 )

def test_time_remaining_never_zero( tmp_path ):
    run = _fake_run( tmp_path, { 'a' : 2000.0 } )
    _start( tmp_path, 'a', 1.9 )
    eta, _ = run.time_remaining()
    assert eta == 1.0

def test_select_tests_by_time():
    sel = testlauncher.select_tests_by_time
    timings = { 'a' : 1000.0, 'b' : 2000.0, 'c' : 3000.0, 'd' : 4000.0, 'e' : 500.0 }
    names = sorted( timings ) + [ 'new1', 'new2' ]
    #Tests without timings are always selected, then the shortest ones:
    assert sel( names, 3.6, 1, timings ) == ( [ 'new1', 'new2', 'e', 'a', 'b' ], [ 'c', 'd' ] )
    assert sel( names, 0.1, 1, timings ) == ( [ 'new1', 'new2' ], [ 'e', 'a', 'b', 'c', 'd' ] )
    assert sel( names, 100, 1, timings ) == ( [ 'new1', 'new2', 'e', 'a', 'b', 'c', 'd' ], [] )
    #With parallel processes (e:0.5+b:2 and a:1+c:3 fit within 4s, d does not):
    assert sel( names, 4.0, 2, timings ) == ( [ 'new1', 'new2', 'e', 'a', 'b', 'c' ], [ 'd' ] )
    #A test longer than the budget is never selected:
    assert sel( [ 'd' ], 3.9, 8, timings ) == ( [], [ 'd' ] )
