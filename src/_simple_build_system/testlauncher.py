#!/usr/bin/env python3
def perform_tests(testdir,
                  installdir, njobs, nexcerpts, filters,
                  do_pycoverage, pkgloader=None, report_spec=None,
                  interactive_ui=None, start_interactive=False,
                  test_order='slowest', test_time=None):
    #When running in a terminal, the tests are run in the background, while
    #showing their progress. If interactive_ui is given, the user can press a
    #key to call interactive_ui(run,stop_on_quit=False), where run is the
    #BackgroundTestRun object (to browse results as they become available). If
    #start_interactive is True, interactive_ui(run,stop_on_quit=True) is called
    #directly, and the report is then not printed.
    import os
    import sys
    import shlex
    import pathlib
    from .conf import runnable_is_test
    from .utils import mkdir_p
    from .utils import system
    from . import dirs
    from . import io as _io
    _ospathjoin=os.path.join

    print = _io.print

    print(f'Running tests in {testdir}:')
    print()
    sys.stdout.flush()
    sys.stderr.flush()

    assert not os.path.exists(testdir)
    testdir=os.path.abspath(testdir)
    time_started = _now()

    logdir=_ospathjoin(installdir,'tests/testref')
    #bindirs=[_ospathjoin(installdir,'bin'),_ospathjoin(installdir,'scripts')]
    logfiles = set(fn for fn in os.listdir(logdir) if fn.endswith('.log')) if os.path.exists(logdir) else set()

    def ldtest(d):
        if os.path.exists(d):
            for f in os.listdir(d):
                if os.path.isdir(_ospathjoin(d,f)):
                    continue#skip some weird .DSYM dirs for fortran apps on osx
                if f+'.log' in logfiles or runnable_is_test(f):
                    yield _ospathjoin(d,f)
    tests=set()
    testinfo = {}
    #Load pkg list from the generated simplebuild.cfg module, for complete
    #consistency between "simplebuild -t" and "sbtests" commands (TODO obsolete
    #requirement?):
    if pkgloader:
        #Called from frontend.py
        pkginfo = dict((p.name,p.info_as_dict()) for p in pkgloader.pkgs)
    else:
        #called from CLI sbtests:
        #FIXME: supported?
        sys.path.insert(0,str(dirs.installdir/'python'))
        import simplebuild.cfg as simplebuild_cfg#FIXME: Could/should we brute-force load via importlib, so avoid poluting the module space here?
        sys.path.pop(0)
        pkginfo = simplebuild_cfg.pkgs

    _selected, nfiltered = select_tests( pkginfo, filters )
    for runnable, pkgname in _selected.items():
        tests.add(runnable)
        testinfo[runnable] = {'pkgname':pkgname}

    #Only run the shortest tests if requested (--testtime):
    ntimeskipped, time_all_s, nunknown = 0, 0.0, 0
    if test_time is not None and tests:
        _timings = load_test_timings()
        _sel, _skipped = select_tests_by_time( tests, test_time, njobs, _timings )
        if _skipped:
            #For the report: how long it would take to wait for all tests:
            time_all_s = estimate_walltime( [ _timings[t] * 0.001 for t in tests
                                              if t in _timings ], njobs )
            nunknown = sum( 1 for t in tests if t not in _timings )
        tests = set( _sel )
        ntimeskipped = len( _skipped )

    mkdir_p(testdir)
    def save_runinfo():
        #Information needed for reporting the results later:
        from . import db
        _write_runinfo( testdir, dict(
            time_started = time_started,
            time_finished = _now(),
            filters = list( filters or [] ),
            nfiltered = nfiltered,
            test_time = test_time,
            ntimeskipped = ntimeskipped,
            time_all_s = time_all_s,
            time_all_nunknown = nunknown,
            njobs = njobs,
            tests = dict( ( t, dict( pkgname = testinfo[t]['pkgname'],
                                     has_reflog = t+'.log' in logfiles ) )
                          for t in sorted(tests) ),
            pkg2timestamp = _pkg_timestamps( db.db ) ) )

    if not tests:
        save_runinfo()
        #Always produce the junit XML file (scripts might expect it):
        _write_junit_xml( testdir )
        if report_spec and report_spec.get('interactive'):
            return None
        return print_report( testdir, logdir, nexcerpts, report_spec )

    _pyexec = shlex.quote( sys.executable or 'python3' )
    import io
    mf = io.StringIO()

    mf.write('TESTDIR:=%s\n\n'%os.path.abspath(testdir))

    mf.write('.DEFAULT: all\n\n')
    mf.write('.PHONY: all\n\n')

    alltests=[]

    if do_pycoverage:
        try:
            import coverage # noqa F401
        except ImportError:
            raise SystemError('Coverage testing requires the Python'
                              ' coverage package. Install with "conda'
                              ' install -c conda-forge coverage" or '
                              '"python3 -mpip install coverage".')
        coverage_out_dir = pathlib.Path(testdir) / 'pycoverage'
        coverage_out_dir.mkdir(parents=True, exist_ok=False)
        coverage_all_out_files = []

    for t in order_tests( tests, test_order ):
        bn=os.path.basename(t)
        td=_ospathjoin(testdir,bn)
        mkdir_p(td)
        tf = io.StringIO()
        tf.write('#!/usr/bin/env bash\n')
        cmdstr = bn
        if do_pycoverage:
            _whichbn = _ospathjoin(installdir,'scripts',bn)
            #_whichbn = shutil.which(bn) <-- no longer works, not in PATH yet
            _ = pathlib.Path( _whichbn ) if _whichbn else None
            if _ and _.exists() and _.read_bytes().startswith(b'#!/usr/bin/env python3'):
                coverage_outfile = coverage_out_dir / ('%s.coverage'%bn)
                coverage_all_out_files.append( coverage_outfile )
                cmdstr = '%s -m coverage run --data-file=%s %s'%(_pyexec,coverage_outfile,_whichbn)
        tf.write('mkdir rundir && cd rundir && touch ../time_start && %s &> ../output.log \n'%cmdstr)
        tf.write('EC=$?\n')
        tf.write('touch ../time_end\n')
        tf.write('echo $EC > ../ec.txt\n')
        tf.write('%s -c \'import os.path;print(1000.0*(os.path.getmtime("../time_end")-os.path.getmtime("../time_start")))\' > ../timing_ms\n'%_pyexec)
        pathlib.Path(td,'run.sh').write_text( tf.getvalue() )

        alltests+=[bn]
        mf.write('.PHONY: %s\n\n'%bn)
        mf.write('%s:\n'%bn)
        mf.write('\t@cd ${TESTDIR}/%s && chmod +x run.sh && ./run.sh'%bn)
        mf.write('\n\n')

    mf.write('all: %s\n\n'%(' '.join(alltests)))
    pathlib.Path(testdir,'Makefile').write_text( mf.getvalue() )

    show_progress = ( not start_interactive and sys.stdout.isatty()
                      and sys.stdin.isatty() and not _io.is_quiet() )
    if start_interactive or show_progress:
        save_runinfo()#so the results can be shown while the tests run
        run = BackgroundTestRun( testdir, installdir, dirs.blddir, alltests,
                                 njobs, is_rerun = False, order = test_order )
        run.start()
        try:
            if start_interactive:
                interactive_ui( run, stop_on_quit = True )
            else:
                _show_progress( run, interactive_ui )
        finally:
            run.stop()
        ec_make = 1 if run.stopped else 0
    else:
        ec_make=system('make -j%i -k -f %s/Makefile all'%(njobs,testdir),
                       env = test_environment() )
    #Compare the output of successful tests with their reference logs (if
    #any). This is done exactly, but with a note in the refdiff.log file if
    #there are only differences in whitespace:
    from .reflogdiff import compare_and_write_diff
    for t in alltests:
        td=_ospathjoin(testdir,t)
        if ( t+'.log' in logfiles
             and _read_number( _ospathjoin(td,'ec.txt'), int ) == 0 ):
            same = compare_and_write_diff( _ospathjoin(logdir,t+'.log'),
                                           _ospathjoin(td,'output.log'),
                                           _ospathjoin(td,'refdiff.log') )
            pathlib.Path(td,'ecdiff.txt').write_text('0\n' if same else '1\n')
    save_runinfo()
    update_test_timings( testdir, alltests )

    notes = []
    if do_pycoverage:
         _cov_infiles = ' '.join(shlex.quote(str(e.absolute().resolve())) for e in coverage_all_out_files)
         _cov_outfile = coverage_out_dir / 'combined.coverage'
         ec = system(f'cd {shlex.quote(str(coverage_out_dir))} && '
                     f'{_pyexec} -mcoverage combine --keep --data-file={shlex.quote(str(_cov_outfile.name))} {_cov_infiles}')
         if ec!=0:
             print("ERROR: py-coverage combine step failed!")
         else:
             reportdir_quoted = shlex.quote(str((coverage_out_dir/"htmlreport").absolute().resolve()))
             ec = system(f'{_pyexec} -mcoverage html '
                         f'--data-file={shlex.quote(str(_cov_outfile.absolute().resolve()))}'
                         f'  --directory={reportdir_quoted} --ignore-errors')
             if ec!=0:
                 print("ERROR: py-coverage html report generation failed!")
             else:
                 notes.append(f"Pycoverage report available in: {reportdir_quoted}/index.html")

    assert len(alltests)==len(set(alltests))

    outfile = _write_junit_xml( testdir )
    notes.append(f'Test results are also summarised in: {outfile.name}')

    sys.stdout.flush()
    sys.stderr.flush()
    if report_spec and report_spec.get('interactive'):
        #The report is printed after the interactive session:
        for n in notes:
            print(f'  {n}')
            print()
        return None
    return print_report( testdir, logdir, nexcerpts, report_spec,
                         notes = notes, failed = ( ec_make != 0 ) )

def _show_progress( run, interactive_ui = None ):
    """Show progress of tests running in the background, on a single line which
    is updated in place. If interactive_ui is given, pressing "i" opens the
    interactive test report (while the tests continue to run)."""
    import sys
    import select
    import termios
    import tty
    from .testreportui import format_duration
    fd = sys.stdin.fileno()
    try:
        old_attrs = termios.tcgetattr( fd )
    except termios.error:
        old_attrs = None
    prevlen = [0]
    def show( final = False ):
        ndone, nrunning, ntot = run.counts()
        nfailed = sum( 1 for n in run.names if run.status( n ) == 'done'
                       and ( _read_number( run.testdir / n / 'ec.txt', int ) != 0
                             or _read_number( run.testdir / n / 'ecdiff.txt', int ) ) )
        from .io import print_prefix
        line = f'{print_prefix} Tests done: {ndone}/{ntot}'
        if nrunning:
            line += f', {nrunning} running'
        if nfailed:
            line += f', {nfailed} failed'
        eta, nunknown = run.time_remaining()
        if not final and eta is not None:
            line += f', ~{format_duration(eta)} left'
            if nunknown:
                line += f' (+{nunknown} without previous timings)'
        if not final and interactive_ui:
            line += '  [press i for interactive view]'
        sys.stdout.write( '\r' + line.ljust( prevlen[0] ) + ( '\n' if final else '' ) )
        sys.stdout.flush()
        prevlen[0] = len(line)
    def cbreak():
        if old_attrs is not None:
            tty.setcbreak( fd )
    def restore():
        if old_attrs is not None:
            termios.tcsetattr( fd, termios.TCSADRAIN, old_attrs )
    cbreak()
    try:
        while run.poll():
            show()
            r, _, _ = select.select( [ fd ], [], [], 0.5 )
            if r:
                key = sys.stdin.read( 1 )
                if interactive_ui and key in ( 'i', 'I' ):
                    restore()
                    sys.stdout.write( '\n' )
                    interactive_ui( run, stop_on_quit = False )
                    prevlen[0] = 0
                    cbreak()
        show( final = True )
        prevlen[0] = 0
    finally:
        restore()
        if prevlen[0]:
            #Interrupted (e.g. by CTRL-C), so end the progress line before
            #any other output:
            sys.stdout.write( '\n' )
            sys.stdout.flush()

def select_tests_by_time( names, budget_s, njobs, timings ):
    """Select tests to run within approximately budget_s seconds (with njobs
    parallel processes), based on their timings in previous runs (in
    milliseconds). Tests without previous timings are always selected (their
    duration is unknown, so they are not included in the estimate), while the
    shortest of the other tests are selected as long as the estimated total
    time (with each test assigned to the least busy process) fits within the
    budget. Returns (selected,skipped), with the skipped tests ordered by
    increasing duration."""
    import heapq
    selected = sorted( n for n in names if n not in timings )
    known = sorted( ( n for n in names if n in timings ),
                    key = lambda n : ( timings[n], n ) )
    slots = [ 0.0 ] * max( 1, njobs )#busy time of each process (a heap)
    for i, n in enumerate( known ):
        t = timings[n] * 0.001
        if slots[0] + t > budget_s:
            #Tests are sorted by duration, so no other test fits either:
            return selected, known[i:]
        heapq.heapreplace( slots, slots[0] + t )
        selected.append( n )
    return selected, []

def estimate_walltime( durations, njobs ):
    """Estimated time to run tests with the given durations (in seconds) with
    njobs parallel processes, when starting the slowest tests first."""
    import heapq
    slots = [ 0.0 ] * max( 1, njobs )
    for t in sorted( durations, reverse = True ):
        heapq.heapreplace( slots, slots[0] + t )
    return max( slots )

def select_tests( pkginfo, filters ):
    """Select the tests to run from the enabled packages (pkginfo is a dict
    with package info dicts as values), according to the filters (patterns from
    --testfilter, or None). Returns a dict mapping the names of the selected
    tests to the names of their packages, and the number of tests not selected
    due to the filters."""
    from .conf import runnable_is_test
    filter_fct = make_filter_fct( filters )
    selected, nfiltered = {}, 0
    for p in ( p for p in pkginfo.values() if p['enabled'] ):
        reflogs, runnables = p['reflogs'], p['runnables']
        for runnable in runnables:
            if '%s.log'%runnable in reflogs or runnable_is_test( runnable ):
                if not filter_fct( runnable ):
                    nfiltered += 1
                else:
                    assert runnable not in selected
                    selected[runnable] = p['name']
    return selected, nfiltered

def _write_junit_xml( testdir ):
    """Write the results of the tests in testdir in junit XML format. Returns
    the path to the created file."""
    import os
    import pathlib
    from . import testxml
    runinfo, results = load_results( testdir )
    testxmlwriter = testxml.TestXMLWriter()
    for r in ( results or [] ):
        test = testxml.Test(r.name,r.pkgname,r.time_ms*0.001)
        if r.ec != 0:
            test.set_run_failure(os.path.join(testdir,r.name,'output.log'))
        elif r.logdiff_failed:
            test.set_reflog_failure(os.path.join(testdir,r.name,'refdiff.log'))
        testxmlwriter.add_test(test)
    outfile = pathlib.Path(testdir) / 'simplebuild_test_results_junitformat.xml'
    with outfile.open('wt') as f:
        for line in testxmlwriter.generate_xml():
            f.write('%s\n'%line)
    return outfile

test_orders = ( 'slowest', 'fastest' )

def order_tests( names, order, timings = None ):
    """Order tests for starting them, based on their timings in previous runs.
    By default ("slowest"), the slowest tests are started first, to avoid
    ending up waiting for a slow test started late. Tests without previous
    timings might also be slow, so they are started first. With "fastest", the
    fastest tests are started first (to get results as quickly as possible),
    and those without previous timings last."""
    assert order in test_orders
    if timings is None:
        timings = load_test_timings()
    def key( t ):
        tprev = timings.get( t )
        if order == 'fastest':
            return ( 1, 0.0, t ) if tprev is None else ( 0, tprev, t )
        return ( 0, 0.0, t ) if tprev is None else ( 1, -tprev, t )
    return sorted( names, key = key )

def test_environment():
    """Environment in which tests are run."""
    from .envsetup import create_install_env_clone
    test_env = create_install_env_clone()
    test_env['DISPLAY']=''
    test_env['PYTHONUNBUFFERED']='1'
    return test_env

def _clear_test_results( testdir, blddir, name ):
    #Remove results of a previous run of the test (but keep the run.sh script):
    from .utils import remove_within
    td = testdir / name
    for f in td.iterdir():
        if f.name != 'run.sh':
            remove_within( f, blddir )

def _compare_with_reflog( testdir, installdir, name ):
    #Compare the output of the test with its reference log (if any, and if the
    #test succeeded):
    import pathlib
    td = pathlib.Path(testdir) / name
    reflog = pathlib.Path(installdir) / 'tests' / 'testref' / f'{name}.log'
    if _read_number( td / 'ec.txt', int ) == 0 and reflog.exists():
        from .reflogdiff import compare_and_write_diff
        same = compare_and_write_diff( reflog, td/'output.log', td/'refdiff.log' )
        ( td / 'ecdiff.txt' ).write_text('0\n' if same else '1\n')

def _record_reruns( testdir, names ):
    #Record in the information about the test run that tests were run again:
    import json
    try:
        with ( testdir / _runinfo_filename ).open() as fh:
            runinfo = json.load( fh )
        t = _now()
        for name in names:
            runinfo.setdefault( 'reruns', {} )[name] = t
        _write_runinfo( testdir, runinfo )
    except (OSError,ValueError):
        pass

def rerun_test( testdir, installdir, blddir, name ):
    """Run a single test from the last test run again (with the current
    installation), and update its results. Returns the exit code of the test
    (or None if it could not be run)."""
    import pathlib
    import subprocess
    testdir = pathlib.Path(testdir)
    td = testdir / name
    if not ( td / 'run.sh' ).is_file() or not ( testdir / 'Makefile' ).is_file():
        return None
    _clear_test_results( testdir, blddir, name )
    subprocess.run( [ 'make', '-f', str(testdir/'Makefile'), name ],
                    env = test_environment(), stdin = subprocess.DEVNULL,
                    stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL )
    _compare_with_reflog( testdir, installdir, name )
    update_test_timings( testdir, [ name ] )
    _record_reruns( testdir, [ name ] )
    return _read_number( td / 'ec.txt', int )

class BackgroundTestRun:

    """Run tests from the Makefile of the last test run in the background
    (used by the interactive test report, to show results as they become
    available). Tests are started with the slowest first (based on previous
    timings), and their output is compared with any reference logs as they
    finish."""

    def __init__( self, testdir, installdir, blddir, names, njobs,
                  is_rerun = True, order = 'slowest' ):
        import pathlib
        self.testdir = pathlib.Path(testdir)
        self.installdir = installdir
        self.blddir = blddir
        self.njobs = max( 1, njobs )
        self.is_rerun = is_rerun
        self.timings = load_test_timings()#from before this run
        self.names = order_tests( names, order, self.timings )
        self._proc = None
        self._compared = set()
        self._finished = False
        self.stopped = False

    def start( self ):
        import subprocess
        if self.is_rerun:
            for name in self.names:
                _clear_test_results( self.testdir, self.blddir, name )
        with ( self.testdir / 'make_output.log' ).open( 'wb' ) as fh:
            self._proc = subprocess.Popen(
                [ 'make', '-j%i'%self.njobs, '-k', '-f',
                  str( self.testdir / 'Makefile' ) ] + self.names,
                env = test_environment(), stdin = subprocess.DEVNULL,
                stdout = fh, stderr = subprocess.STDOUT,
                start_new_session = True )

    def status( self, name ):
        """One of 'waiting', 'running', or 'done'."""
        td = self.testdir / name
        if ( td / 'ec.txt' ).exists():
            return 'done'
        if ( td / 'time_start' ).exists() and not self._finished:
            return 'running'
        return 'done' if self._finished else 'waiting'

    @property
    def active( self ):
        return self._proc is not None and not self._finished

    def poll( self ):
        """Update the results of finished tests. Returns True while the run is
        still active."""
        if self._finished or self._proc is None:
            return False
        running = self._proc.poll() is None
        for name in self.names:
            if name not in self._compared and self.status( name ) == 'done':
                if ( self.testdir / name / 'timing_ms' ).exists() or not running:
                    _compare_with_reflog( self.testdir, self.installdir, name )
                    self._compared.add( name )
        if not running:
            self._finish()
        return running

    def counts( self ):
        """Returns (ndone,nrunning,ntotal)."""
        st = [ self.status( n ) for n in self.names ]
        return st.count('done'), st.count('running'), len(st)

    def time_remaining( self ):
        """Estimated remaining time in seconds (based on the timings of the
        tests in previous runs), and the number of unfinished tests without
        previous timings (which are not included in the estimate). Returns
        (None,n) if the remaining time is unknown (i.e. if all unfinished
        tests either have no previous timings, or are already running for
        longer than in previous runs)."""
        import time
        work, longest, nunknown, nknown = 0.0, 0.0, 0, 0
        for name in self.names:
            st = self.status( name )
            if st == 'done':
                continue
            tprev = self.timings.get( name )
            if tprev is None:
                nunknown += 1
                continue
            remaining = tprev * 0.001
            if st == 'running':
                try:
                    started = ( self.testdir / name / 'time_start' ).stat().st_mtime
                    remaining -= time.time() - started
                except OSError:
                    pass
                if remaining <= 0.0:
                    #Already running longer than previously, so the remaining
                    #time is unknown:
                    continue
            nknown += 1
            work += remaining
            longest = max( longest, remaining )
        if not nknown:
            return None, nunknown
        #Never claim that no time is left while tests are still running:
        return max( 1.0, longest, work / self.njobs ), nunknown

    def stop( self ):
        """Stop the run (if still active)."""
        import os
        import signal
        if not self.active:
            return
        self.stopped = True
        try:
            os.killpg( self._proc.pid, signal.SIGTERM )
        except OSError:
            pass
        try:
            self._proc.wait( timeout = 5 )
        except Exception:
            try:
                os.killpg( self._proc.pid, signal.SIGKILL )
            except OSError:
                pass
            self._proc.wait()
        self.poll()

    def wait( self ):
        import time
        while self.poll():
            time.sleep( 0.2 )

    def _finish( self ):
        self._finished = True
        update_test_timings( self.testdir, self.names )
        if self.is_rerun:
            _record_reruns( self.testdir, self.names )

def _test_timings_file():
    #Kept outside the test results directory, which is removed for each run:
    from . import dirs
    return dirs.blddir / 'testtimings.json'

def load_test_timings():
    """Duration in milliseconds of tests in previous runs (dict)."""
    import json
    try:
        with _test_timings_file().open() as fh:
            d = json.load( fh )
    except (OSError,ValueError):
        return {}
    if not isinstance( d, dict ):
        return {}
    return dict( ( k, float(v) ) for k,v in d.items()
                 if isinstance( v, (int,float) ) )

def update_test_timings( testdir, testnames ):
    """Record the durations of the given tests, if they completed (timings of
    other tests are kept)."""
    import os
    import json
    from .utils import write_atomic
    timings = load_test_timings()
    changed = False
    for t in testnames:
        td = os.path.join( testdir, t )
        tms = _read_number( os.path.join( td, 'timing_ms' ), float )
        if tms is not None and _read_number( os.path.join( td, 'ec.txt' ), int ) is not None:
            timings[t] = round( tms, 1 )
            changed = True
    if changed:
        write_atomic( _test_timings_file(),
                      json.dumps( timings, indent = 1, sort_keys = True ) + '\n' )

def _now():
    import datetime
    return datetime.datetime.now().isoformat( timespec = 'seconds' )

def _read_number( fn, numtype ):
    #Missing or invalid result files can happen if tests are killed or the
    #test run is interrupted. Returns None in that case.
    try:
        with open(fn) as fh:
            return numtype(fh.read().strip())
    except (OSError,ValueError):
        return None

def make_filter_fct( filters ):
    """Returns function deciding if a test with a given name passes the
    filters (list of patterns, where patterns with a "!" prefix are negated).
    The same logic as for the pkg_filters is used, i.e. if any positive
    filters are defined, a test must pass at least one of them, and if any
    negative filters are defined, a test must not pass any of them."""
    import fnmatch
    pos_filters, neg_filters = [], []
    for fltr in ( filters or [] ):
        fltr=fltr.strip()
        if fltr.startswith('!'):
            fltr = fltr[1:].strip()
            if fltr:
                neg_filters.append( fltr )
        elif fltr:
            pos_filters.append( fltr )
    def filter_fct( testname ):
        if pos_filters:
            if not any( fnmatch.fnmatch(testname,fltr)
                        for fltr in pos_filters ):
                return False
        if neg_filters:
            if any( fnmatch.fnmatch(testname,fltr)
                    for fltr in neg_filters ):
                return False
        return True
    return filter_fct

_runinfo_filename = 'testrun.json'

def _write_runinfo( testdir, info ):
    import json
    import pathlib
    from .utils import write_atomic
    write_atomic( pathlib.Path(testdir) / _runinfo_filename,
                  json.dumps( info, indent = 1 ) + '\n' )

def _pkg_timestamps( db ):
    #Timestamps of packages (as strings), allowing us to detect if packages
    #were changed (and thus rebuilt) after the tests were run:
    return dict( ( k, repr(v) ) for k,v in db.get('pkg2timestamp',{}).items() )

def packages_changed_since( runinfo ):
    """Names of packages which were changed (and thus rebuilt) after the test
    run described by runinfo."""
    from . import db
    _ts = _pkg_timestamps( db.db )
    return sorted( p for p,t in ( runinfo.get('pkg2timestamp') or {} ).items()
                   if _ts.get(p,t) != t )

class TestResult:

    def __init__( self, name, pkgname, has_reflog, ec, ecdiff, time_ms ):
        self.name = name
        self.pkgname = pkgname
        self.has_reflog = has_reflog
        self.ec = 1 if ec is None else ec#None means that the test was killed
        self.ecdiff = ecdiff
        self.time_ms = time_ms or 0.0

    @property
    def logdiff_failed( self ):
        return bool( self.ecdiff )

    @property
    def failed( self ):
        return self.ec != 0 or self.logdiff_failed

def load_results( testdir ):
    """Load information about the last test run, and the results of the
    tests (list of TestResult objects, sorted by name). Returns (None,None) if
    not available."""
    import json
    import os
    try:
        with open( os.path.join( testdir, _runinfo_filename ) ) as fh:
            runinfo = json.load( fh )
        tests = runinfo['tests']
    except (OSError,ValueError,KeyError,TypeError):
        return None, None
    results = []
    for name, nfo in sorted( tests.items() ):
        td = os.path.join( testdir, name )
        results.append( TestResult( name, nfo.get('pkgname'),
                                    nfo.get('has_reflog'),
                                    _read_number( os.path.join(td,'ec.txt'), int ),
                                    _read_number( os.path.join(td,'ecdiff.txt'), int ),
                                    _read_number( os.path.join(td,'timing_ms'), float ) ) )
    return runinfo, results

_line_hr = " ---------------------------------------+-----------+--------+----------+------------------"
_line_titles = "  Test job results                      | Time [ms] | Job EC | Log-diff | Trouble info"

def print_report( testdir, logdir, nexcerpts, spec, *, filters = None,
                  post_factum = False, notes = (), failed = False ):
    """Print report of the results of the last test run (in testdir), and
    return the exit code (73 in case of failures). The spec is the result of
    parse_args.parse_testreport_spec (None means default settings). If filters
    are given, only tests passing them are shown. If post_factum is True, the
    report is printed independently of a test run, and starts with
    information about the test run. Any notes are printed after the table, and
    failed=True indicates that the test run failed in some other way."""
    import os
    import sys
    from . import io as _io
    from . import col
    print = _io.print
    spec = spec or dict( sort = None, failedonly = False )
    runinfo, results = load_results( testdir )
    if runinfo is None:
        print('No test results are available for this build variant'
              ' (run tests with "-t" first).')
        print()
        return 1
    if post_factum:
        _ = ', '.join( runinfo.get('filters') or [] )
        print('Report of test results from %s%s:'%(
            runinfo.get('time_finished','<unknown>').replace('T',' '),
            f' (tests run with filter "{_}")' if _ else ''))
        print()
        changed = packages_changed_since( runinfo )
        if changed:
            print('%sWARNING%s The results might be outdated, since the following'
                  ' packages were changed\n        after the tests were run: %s'%(
                      col.bad, col.end, ' '.join(changed) ))
            print()
    ntimeskipped = runinfo.get('ntimeskipped',0)
    if ntimeskipped:
        from .testreportui import format_duration
        def _n( n, what ):
            return f'{n} {what}' + ( '' if n == 1 else ( 'es' if what.endswith('s') else 's' ) )
        _nu = runinfo.get('time_all_nunknown',0)
        print('Note: %s not run due to --testtime=%g (running all tests would'
              ' take about %s with %s%s).'%(
                  _n( ntimeskipped, 'test' ) + ( ' was' if ntimeskipped == 1 else ' were' ),
                  runinfo['test_time'],
                  format_duration( runinfo.get('time_all_s',0.0) ),
                  _n( runinfo.get('njobs',1), 'parallel process' ),
                  ( ', plus the time of %s without previous timings'%_n( _nu, 'test' ) )
                  if _nu else '' ) )
        print()
    nfiltered = runinfo.get('nfiltered',0)
    if nfiltered and not results:
        print(f'WARNING: All {nfiltered} tests were blocked by specified filters.')
        print()
    elif nfiltered:
        print(f'Note: {nfiltered} tests were blocked by specified filters.')
        print()
    nall = len(results)
    if filters:
        filter_fct = make_filter_fct( filters )
        results = [ r for r in results if filter_fct( r.name ) ]
    if spec['failedonly']:
        results = [ r for r in results if r.failed ]
    if spec['sort'] == 'time':
        results.sort( key = lambda r : ( -r.time_ms, r.name ) )
    elif spec['sort'] == 'name':
        results.sort( key = lambda r : r.name )
    else:
        #Relevance (the default): Since the end of the output is what remains
        #visible in a terminal, failed tests are put at the bottom, and within
        #each group the slowest tests are put towards the bottom:
        results.sort( key = lambda r : ( r.failed, r.time_ms, r.name ) )
    any_failed = failed
    print(_line_hr)
    print(_line_titles)
    print(_line_hr)
    if not results:
        print('  n/a')
    excerpts_to_print = []
    for r in results:
        ecstr = 'FAIL' if r.ec else ' OK '
        logdiffstr = ' -- '
        if r.ecdiff is not None:
            logdiffstr = 'FAIL' if r.ecdiff else ' OK '
        info = '--'
        if r.failed:
            info = os.path.realpath( os.path.join( testdir, r.name ) )
            any_failed = True
            if nexcerpts > 0:
                excerpts_to_print.append( ( r.name, 'output.log' if r.ec
                                            else 'refdiff.log' ) )
        print("  %-37s |  %6.0f   |  %s  |   %s   | %s"%( r.name, r.time_ms,
                                                       ecstr, logdiffstr, info ))
    print(_line_hr)
    if len(results) != nall:
        print(f'  ({nall-len(results)} of the {nall} tests are not shown)')
    print()
    for n in notes:
        print(f'  {n}')
        print()
    for t, logname in excerpts_to_print:
        print_excerpt( t, testdir, logname, nexcerpts,
                       reflog = os.path.join( logdir, t+'.log' ) )
    sys.stdout.flush()
    sys.stderr.flush()
    if any_failed:
        print('  %sERROR: Some tests failed!%s'%(col.bad,col.end))
        print()
    elif nall == 0:
        print('  No tests were found.')
        print()
    else:
        print('  %sAll tests completed without failures!%s'%(col.ok,col.end))
        print()
    #Used special exit code (73) to indicate test failures.
    return 73 if any_failed else 0

def excerpt_lines( lines, nexcerpts ):
    """The first and last nexcerpts lines (all lines if there are not more
    than twice that number of lines). Returns (head,nomitted,tail)."""
    if len(lines) <= 2*nexcerpts:
        return lines, 0, []
    return lines[:nexcerpts], len(lines) - 2*nexcerpts, lines[-nexcerpts:]

def print_excerpt( testname, testdir, logname, nexcerpts, reflog ):
    """Print excerpt of the output log of a failed test, or of the differences
    between the output and the reference log of the test."""
    import os
    import sys
    from . import io as _io
    from . import col
    from . import reflogdiff
    from . import diffrender
    color = bool(col.end)
    td = os.path.join(testdir,testname)
    output = os.path.join(td,'output.log')
    try:
        if logname == 'refdiff.log':
            ref_lines = reflogdiff.read_lines( reflog )
            out_lines = reflogdiff.read_lines( output )
            note = ( reflogdiff.whitespace_only_note
                     if reflogdiff.differs_only_in_whitespace( ref_lines, out_lines )
                     else None )
            lines = [ diffrender.segments_to_text( row, color ) for row in
                      diffrender.changes_rows( ref_lines, out_lines,
                                               note = note ) ]
            descr = 'differences between reference log and output'
        else:
            lines = [ diffrender.visible_text( line.rstrip('\n') ) for line
                      in reflogdiff.read_lines( output ) ]
            descr = 'output'
    except OSError as e:
        _io.print(f'Could not read results of test {testname}: {e}')
        return
    head, nomitted, tail = excerpt_lines( lines, nexcerpts )
    sys.stdout.flush()
    def emit( title, ll ):
        _io.print('\n====>\n====> %s:\n====>'%title)
        sys.stdout.flush()
        for line in ll:
            sys.stdout.write( line + '\n' )
        sys.stdout.flush()
    if not nomitted:
        emit( 'All %i lines of %s of %s'%(len(lines),descr,testname), head )
    else:
        emit( 'First %i lines of %s of %s'%(nexcerpts,descr,testname), head )
        _io.print('====> (%i lines omitted)'%nomitted)
        emit( 'Last %i lines of %s of %s'%(nexcerpts,descr,testname), tail )
    _io.print('====> (end of %s of %s)\n'%(descr,testname))
