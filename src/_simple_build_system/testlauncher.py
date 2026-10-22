#!/usr/bin/env python3
def perform_tests(testdir,
                  installdir, njobs, nexcerpts, filters,
                  do_pycoverage, pkgloader=None, report_spec=None):
    import os
    import sys
    import shlex
    import pathlib
    from .conf import runnable_is_test
    from .utils import mkdir_p
    from .utils import system
    from . import testxml
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

    filter_fct = make_filter_fct( filters )

    nfiltered = 0
    for p in (p for _,p in pkginfo.items() if p['enabled']):
        reflogs, runnables = p['reflogs'],p['runnables']
        for runnable in runnables:
            hasreflog = '%s.log'%runnable in reflogs
            if hasreflog or runnable_is_test(runnable):
                if not filter_fct( runnable ):
                    nfiltered += 1
                else:
                    assert runnable not in tests
                    tests.add(runnable)
                    testinfo[runnable] = {'pkgname':p['name']}

    mkdir_p(testdir)
    def save_runinfo():
        #Information needed for reporting the results later:
        from . import db
        _write_runinfo( testdir, dict(
            time_started = time_started,
            time_finished = _now(),
            filters = list( filters or [] ),
            nfiltered = nfiltered,
            tests = dict( ( t, dict( pkgname = testinfo[t]['pkgname'],
                                     has_reflog = t+'.log' in logfiles ) )
                          for t in sorted(tests) ),
            pkg2timestamp = _pkg_timestamps( db.db ) ) )

    if not tests:
        save_runinfo()
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

    #Start the slowest tests first (based on their timings in previous runs),
    #to avoid ending up waiting for a slow test started late. Tests without
    #previous timings might also be slow, so they are started first:
    timings = load_test_timings()
    def _slowest_first( t ):
        tprev = timings.get( t )
        return ( 0, 0.0, t ) if tprev is None else ( 1, -tprev, t )

    for t in sorted( tests, key = _slowest_first ):
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

    from .envsetup import create_install_env_clone
    test_env = create_install_env_clone()
    test_env['DISPLAY']=''
    test_env['PYTHONUNBUFFERED']='1'
    ec_make=system('make -j%i -k -f %s/Makefile all'%(njobs,testdir), env = test_env )
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

    #Results in junit XML format:
    runinfo, results = load_results( testdir )
    testxmlwriter = testxml.TestXMLWriter()
    for r in results:
        test = testxml.Test(r.name,r.pkgname,r.time_ms*0.001)
        if r.ec != 0:
            test.set_run_failure(_ospathjoin(testdir,r.name,'output.log'))
        elif r.logdiff_failed:
            test.set_reflog_failure(_ospathjoin(testdir,r.name,'refdiff.log'))
        testxmlwriter.add_test(test)
    outfile = pathlib.Path(testdir) / 'simplebuild_test_results_junitformat.xml'
    with outfile.open('wt') as f:
        for line in testxmlwriter.generate_xml():
            f.write('%s\n'%line)
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

def rerun_test( testdir, installdir, blddir, name ):
    """Run a single test from the last test run again (with the current
    installation), and update its results. Returns the exit code of the test
    (or None if it could not be run)."""
    import os
    import json
    import pathlib
    import subprocess
    from .utils import remove_within
    from .envsetup import create_install_env_clone
    testdir = pathlib.Path(testdir)
    td = testdir / name
    if not ( td / 'run.sh' ).is_file() or not ( testdir / 'Makefile' ).is_file():
        return None
    for f in td.iterdir():
        if f.name != 'run.sh':
            remove_within( f, blddir )
    test_env = create_install_env_clone()
    test_env['DISPLAY']=''
    test_env['PYTHONUNBUFFERED']='1'
    subprocess.run( [ 'make', '-f', str(testdir/'Makefile'), name ],
                    env = test_env, stdin = subprocess.DEVNULL,
                    stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL )
    ec = _read_number( td / 'ec.txt', int )
    reflog = pathlib.Path(installdir) / 'tests' / 'testref' / f'{name}.log'
    if ec == 0 and reflog.exists():
        from .reflogdiff import compare_and_write_diff
        same = compare_and_write_diff( reflog, td/'output.log', td/'refdiff.log' )
        ( td / 'ecdiff.txt' ).write_text('0\n' if same else '1\n')
    update_test_timings( testdir, [ name ] )
    #Record in the information about the test run:
    try:
        with open( os.path.join( testdir, _runinfo_filename ) ) as fh:
            runinfo = json.load( fh )
        runinfo.setdefault( 'reruns', {} )[name] = _now()
        _write_runinfo( testdir, runinfo )
    except (OSError,ValueError):
        pass
    return ec

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
    spec = spec or dict( sort = 'name', failedonly = False )
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
    if spec['sort'] == 'pkg':
        results.sort( key = lambda r : ( r.pkgname or '', r.name ) )
    elif spec['sort'] == 'time':
        results.sort( key = lambda r : ( -r.time_ms, r.name ) )
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
