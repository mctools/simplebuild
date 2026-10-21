#!/usr/bin/env python3
def perform_tests(testdir,
                  installdir, njobs, nexcerpts, filters,
                  do_pycoverage, pkgloader=None):
    import os
    import sys
    import fnmatch
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

    from . import col as _col
    col_ok = _col.ok
    col_bad = _col.bad
    col_end = _col.end

    print(f'Running tests in {testdir}:')
    print()
    sys.stdout.flush()
    sys.stderr.flush()

    assert not os.path.exists(testdir)
    testdir=os.path.abspath(testdir)
    line_hr = " ---------------------------------------+-----------+--------+----------+------------------"
    line_titles = "  Test job results                      | Time [ms] | Job EC | Log-diff | Trouble info"
    def print_header():
        print(line_hr)
        print(line_titles)
        print(line_hr)
    def print_footer():
        print(line_hr)

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

    if filters:
        # Use same logic as for the pkg_filters, i.e.:

        # * If any positive filters are defined, a pkg must pass at least one of
        #   them to pass.
        # * If any negative filters are defined, a pkg must NOT pass any of
        #   them, to pass.

        _pos_filters = []
        _neg_filters = []
        for fltr in filters:
            fltr=fltr.strip()
            if fltr.startswith('!'):
                fltr = fltr[1:].strip()
                if fltr:
                    _neg_filters.append( fltr )
            elif fltr:
                _pos_filters.append( fltr )
        def filter_fct( testname ):
            if _pos_filters:
                if not any( fnmatch.fnmatch(testname,fltr)
                            for fltr in _pos_filters ):
                    return False
            if _neg_filters:
                if any( fnmatch.fnmatch(testname,fltr)
                        for fltr in _neg_filters ):
                    return False
            return True
    else:
        def filter_fct( testname ):
            return True


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

    if not tests:
        if nfiltered:
            print(f'WARNING: All {nfiltered} tests were blocked by specified filters.')
            print()
        print_header()
        print('  n/a')
        print_footer()
        return 0

    mkdir_p(testdir)
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

    for t in tests:
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
    ec_global=system('make -j%i -k -f %s/Makefile all'%(njobs,testdir), env = test_env )
    def read_number( fn, numtype ):
        #Missing or invalid result files can happen if tests are killed or the
        #test run is interrupted. Returns None in that case.
        try:
            with open(fn) as fh:
                return numtype(fh.read().strip())
        except (OSError,ValueError):
            return None
    #Compare the output of successful tests with their reference logs (if
    #any). This is done exactly, but with a note in the refdiff.log file if
    #there are only differences in whitespace:
    from .reflogdiff import compare_and_write_diff
    for t in alltests:
        td=_ospathjoin(testdir,t)
        if ( t+'.log' in logfiles
             and read_number( _ospathjoin(td,'ec.txt'), int ) == 0 ):
            same = compare_and_write_diff( _ospathjoin(logdir,t+'.log'),
                                           _ospathjoin(td,'output.log'),
                                           _ospathjoin(td,'refdiff.log') )
            pathlib.Path(td,'ecdiff.txt').write_text('0\n' if same else '1\n')
    rep=[]
    for t in alltests:
        td=_ospathjoin(testdir,t)
        ecdiff = read_number( _ospathjoin(td,'ecdiff.txt'), int )
        ec = read_number( _ospathjoin(td,'ec.txt'), int )
        rep+=[(t, 1 if ec is None else ec, ecdiff)]
    rep.sort()
    excerpts_to_print=[]
    if nfiltered:
        print(f'Note: {nfiltered} tests were blocked by specified filters.')
        print()
    print_header()
    for t,ec,ecdiff in rep:
        time_ms = read_number( _ospathjoin(testdir,t,'timing_ms'), float ) or 0.0
        ecstr='FAIL' if ec else ' OK '
        logdiffstr=' -- '
        if ecdiff is not None:
            logdiffstr='FAIL' if ecdiff else ' OK '
        info='--'
        if ec!=0 or ( (ecdiff is not None) and ecdiff):
            info=os.path.realpath(_ospathjoin(testdir,t))
            ec_global=1
            if nexcerpts>0:
                excerpts_to_print += [(t,testdir,'output.log' if ec!=0 else 'refdiff.log')]
        print("  %-37s |  %6.0f   |  %s  |   %s   | %s"%(t,time_ms,ecstr,logdiffstr,info))
        logdiffok = (ecdiff is None or not ecdiff)
        testinfo[t].update( dict(time_ms = time_ms,
                                 exitcode = ec,
                                 logfile = _ospathjoin(testdir,t,'output.log'),
                                 logdiffok = logdiffok,
                                 logdifffile = (_ospathjoin(testdir,t,'refdiff.log') if not logdiffok else None)))
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
                 print(f"Pycoverage report available in: {reportdir_quoted}/index.html")

    assert len(alltests)==len(set(alltests))

    print_footer()

    do_junitxml = True
    if do_junitxml:
        testxmlwriter = testxml.TestXMLWriter()
        for testcmd in tests:
            nfo = testinfo[testcmd]
            test = testxml.Test(testcmd,nfo['pkgname'],nfo['time_ms']*0.001)
            if nfo['exitcode'] != 0:
                test.set_run_failure(nfo['logfile'])
            elif not nfo['logdiffok']:
                test.set_reflog_failure(nfo['logdifffile'])
            testxmlwriter.add_test(test)
        outfile = pathlib.Path(testdir) / 'simplebuild_test_results_junitformat.xml'
        with outfile.open('wt') as f:
            for line in testxmlwriter.generate_xml():
                f.write('%s\n'%line)
        print()
        print(f'  Test results are also summarised in: {outfile.name}')
        print()

    if excerpts_to_print:
        for t,testdir,logname in excerpts_to_print:
            print_excerpt( t, testdir, logname, nexcerpts,
                           reflog = _ospathjoin(logdir,t+'.log') )

    sys.stdout.flush()
    sys.stderr.flush()

    if ec_global:
        print('  %sERROR: Some tests failed!%s'%(col_bad,col_end))
        print()
    else:
        print('  %sAll tests completed without failures!%s'%(col_ok,col_end))
        print()
    #Used special exit code (73) to indicate test failures.
    return 0 if ec_global==0 else 73

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
