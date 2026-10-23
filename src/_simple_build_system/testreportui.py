# Curses based interactive test report ("sb --testreport=interactive"),
# showing the results of the last test run in a table, from which the output
# of tests or differences with reference logs can be inspected, and tests can
# be run again.

from .cursesbase import ScreenBase, OutputView, run_curses_app, QuitApp, is_back_key

_sort_orders = ( 'relevance', 'time', 'name' )

_keyhelp = [
    ( 'q', 'Quit' ),
    ( 'arrows, j k', 'Select test (also PgUp/PgDn/Space and Home/End)' ),
    ( 'Enter', 'Show differences with the reference log (if any), otherwise the output' ),
    ( 'o', 'Show the output of the test' ),
    ( 's', 'Change sort order (relevance: running, failed, waiting, successful; slowest first; name)' ),
    ( 'f', 'Show only failed tests, or all tests' ),
    ( 'r', 'Run the selected test again' ),
    ( 'b', 'Rebuild (as with "sb"), and run the selected test again' ),
    ( 'e', 'Show the output of the last rebuild (e.g. compilation errors)' ),
    ( 't', 'Run the shown tests again in the background (results appear as they finish)' ),
    ( 'c', 'Cancel tests running in the background' ),
    ( '?', 'Show this help' ),
    ( '', 'Letter keys work the same independently of Shift and Caps Lock.' ),
]

_statusbar = ( 'q:quit  Enter:inspect  o:output  s:sort  f:failed only'
               '  r:rerun  b:rebuild+rerun  e:build log  t:run tests  c:cancel  ?:help' )

def format_duration( seconds ):
    s = int( seconds + 0.5 )
    if s < 60:
        return f'{s}s'
    if s < 3600:
        return '%im%02is'%( s // 60, s % 60 )
    return '%ih%02im'%( s // 3600, ( s % 3600 ) // 60 )

class TestReportUI( ScreenBase ):

    def __init__( self, stdscr, report ):
        super().__init__( stdscr )
        self.report = report
        self.sort = report.spec['sort'] or 'relevance'
        self.failedonly = report.spec['failedonly']
        self.isel = 0
        self.ytop = 0
        self._load()

    def _load( self ):
        from .testlauncher import load_results, make_filter_fct
        self.runinfo, results = load_results( self.report.testdir )
        filter_fct = make_filter_fct( self.report.filters )
        self.all_results = [ r for r in ( results or [] ) if filter_fct( r.name ) ]

    def _is_pending( self, r ):
        run = self.report.run
        return bool( run and r.name in run.names and run.status( r.name ) != 'done' )

    def rows( self ):
        rr = [ r for r in self.all_results
               if not self.failedonly or ( r.failed and not self._is_pending( r ) ) ]
        if self.sort == 'time':
            rr.sort( key = lambda r : ( -r.time_ms, r.name ) )
        elif self.sort == 'relevance':
            rr.sort( key = lambda r : ( self._status_rank( r ), r.name ) )
        return rr

    def _status_rank( self, r ):
        #Running tests first, then failed, waiting, and successful ones:
        run = self.report.run
        st = run.status( r.name ) if run and r.name in run.names else 'done'
        if st == 'running':
            return 0
        if st == 'waiting':
            return 2
        return 1 if r.failed else 3

    @property
    def selected( self ):
        rows = self.rows()
        if not rows:
            return None
        self.isel = max( 0, min( self.isel, len(rows) - 1 ) )
        return rows[self.isel]

    def select_name( self, name ):
        for i, r in enumerate( self.rows() ):
            if r.name == name:
                self.isel = i
                return

    def body_geometry( self ):
        h, w = self.scr.getmaxyx()
        top = 4
        return top, max( 1, h - top - 2 ), w

    def draw( self ):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        rows = self.rows()
        run = self.report.run
        if run and run.active:
            ndone, nrunning, ntot = run.counts()
            eta, nunknown = run.time_remaining()
            progress = f'running tests: {ndone}/{ntot} done'
            if eta is not None:
                progress += f', ~{format_duration(eta)} left'
                if nunknown:
                    progress += f' (+{nunknown} without previous timings)'
            title = f' sb --testreport   {progress}   sort: {self.sort}'
        else:
            nfailed = sum( 1 for r in self.all_results if r.failed )
            title = ' sb --testreport   %i tests, %i failed   sort: %s'%(
                len(self.all_results), nfailed, self.sort )
        if self.failedonly:
            title += '   (only failed tests shown)'
        self._put( 0, 0, title.ljust( w ), self.attrs['title'] )
        if run and run.active:
            info = 'Tests are running in the background'
        else:
            info = 'Results of test run finished %s'%( ( self.runinfo or {} ).get(
                'time_finished', '<unknown>' ).replace('T',' ') )
        _ = ', '.join( ( self.runinfo or {} ).get('filters') or [] )
        if _:
            info += f' (tests run with filter "{_}")'
        self._put( 1, 0, info, self.attrs['dim'] )
        if self.report.warning:
            self._put( 2, 0, self.report.warning, self.attrs['bad'] )
        namew = max( 20, min( 45, max( [ len(r.name) for r in rows ] + [ 4 ] ) ) )
        pkgw = max( 7, min( 25, max( [ len(r.pkgname or '') for r in rows ] + [ 7 ] ) ) )
        def fmt( name, pkg, time, ec, logdiff ):
            return '  %s  %s  %9s  %6s  %8s'%( name.ljust( namew )[:namew],
                                             pkg.ljust( pkgw )[:pkgw],
                                             time, ec, logdiff )
        self._put( 3, 0, fmt( 'Test', 'Package', 'Time [ms]', 'Job EC', 'Log-diff' ),
                   self.attrs['meta'] )
        top, height, width = self.body_geometry()
        sel = self.selected
        if sel is not None:
            if self.isel < self.ytop:
                self.ytop = self.isel
            elif self.isel >= self.ytop + height:
                self.ytop = self.isel - height + 1
        self.ytop = max( 0, min( self.ytop, max( 0, len(rows) - height ) ) )
        if not rows:
            self._put( top, 2, 'No tests to show.' if not self.failedonly
                       else 'No failed tests.', self.attrs['dim'] )
        run = self.report.run
        for i, r in enumerate( rows[self.ytop:self.ytop+height] ):
            st = run.status( r.name ) if ( run and r.name in run.names ) else 'done'
            if st != 'done':
                line = fmt( r.name, r.pkgname or '', '', st.upper(), '' )
                attr = self.attrs['dim'] if st == 'waiting' else self.attrs['meta']
                if r is sel:
                    attr = self.attrs['selected']
                self._put( top + i, 0, line.ljust( w ), attr )
                continue
            logdiff = '--' if r.ecdiff is None else ( 'FAIL' if r.ecdiff else 'OK' )
            line = fmt( r.name, r.pkgname or '', '%.0f'%r.time_ms,
                        'FAIL' if r.ec else 'OK', logdiff )
            attr = self.attrs['bad'] if r.failed else self.attrs['ok']
            if r is sel:
                attr = self.attrs['selected']
            self._put( top + i, 0, line.ljust( w ), attr )
        self._put( h - 2, 0, self.message, self.attrs['meta'] )
        self._put( h - 1, 0, _statusbar.ljust( w ), self.attrs['title'] )
        self.scr.refresh()

    def show_output( self, r ):
        TestOutputView( self, r.name ).run()
        self._load()
        self.select_name( r.name )

    def inspect( self, r ):
        if r.ec == 0 and r.logdiff_failed:
            self.show_reflog_diff( r )
        else:
            self.show_output( r )

    def show_reflog_diff( self, r ):
        from .reflogupdate import Session
        from .reflogui import ReflogUI
        rep = self.report
        session = Session( rep.testdir, rep.installdir, filters = [ r.name ],
                           rerun_fct = rep.rerun_fct, rebuild_fct = rep.rebuild_fct )
        if not session.candidates:
            self.message = 'The output is identical to the reference log'
            return
        session.code_required = rep.code_required
        try:
            ReflogUI( self.scr, session, title = 'sb --testreport',
                      toplevel = False ).run()
        finally:
            #(also when quitting from the other screen):
            rep.code_required = session.code_required
            for f in session.updated_files:
                if f not in rep.updated_files:
                    rep.updated_files.append( f )
        self.repaint_fully()
        self._load()
        self.select_name( r.name )

    def start_tests( self, names ):
        rep = self.report
        if rep.run and rep.run.active:
            self.message = 'Tests are already running'
            return
        if not names or not rep.start_run_fct:
            self.message = 'No tests to run'
            return
        rep.run = rep.start_run_fct( names )
        self._load()
        self.message = f'Running {len(names)} tests in the background'

    def build_log_path( self ):
        return getattr( self.report.rebuild_fct, 'log_path', None )

    def rerun( self, r, rebuild ):
        rep = self.report
        if rebuild:
            def do_rebuild():
                print(f'Rebuilding before running {r.name} again...', flush = True)
                return rep.rebuild_fct()
            if not self.run_outside_curses( do_rebuild ):
                self.show_build_log( self.build_log_path(), failed = True )
                self.message = 'Build failed'
                return
        self.message = f'Running {r.name} again...'
        self.draw()
        ec = rep.rerun_fct( r.name )
        self._load()
        self.select_name( r.name )
        if ec is None:
            self.message = 'Could not run the test'
            return
        r2 = next( ( e for e in self.all_results if e.name == r.name ), None )
        self.message = ( f'{r.name} now ' + ( 'FAILS' if ( r2 is None or r2.failed )
                                             else 'passes' ) )
        if r2 is not None and not r2.failed and self.failedonly:
            self.message += ' (and is no longer shown, press f to show all tests)'

    def run( self ):
        try:
            self._run()
        except QuitApp:
            pass
        #Stop tests running in the background, unless they were started before
        #the user interface was opened and should continue:
        run = self.report.run
        if run and run.active and ( self.report.stop_on_quit
                                    or run is not self.report.initial_run ):
            run.stop()

    def _run( self ):
        c = self.curses
        self.hide_cursor()
        self.scr.keypad( True )
        self.message = 'Press ? for help'
        while True:
            run = self.report.run
            self.scr.timeout( 500 if ( run and run.active ) else -1 )
            self.draw()
            ch = self.getkey()
            _, height, _ = self.body_geometry()
            if ch == -1:
                #Timeout while tests are running in the background:
                if run and not run.poll():
                    self.message = ( 'The tests were cancelled' if run.stopped
                                     else 'All tests finished' )
                #Keep the same test selected, even if the rows are reordered:
                sel = self.selected
                selname = sel.name if sel else None
                self._load()
                if selname:
                    self.select_name( selname )
                continue
            self.message = ''
            sel = self.selected
            if ch == ord('q'):
                return
            elif is_back_key( ch ):
                self.message = 'Press q to quit'
            elif ch == ord('t'):
                self.start_tests( [ r.name for r in self.rows() ] )
            elif ch == ord('c'):
                if run and run.active:
                    run.stop()
                    self._load()
                    self.message = 'The tests were cancelled'
                else:
                    self.message = 'No tests are running'
            elif ch in ( c.KEY_DOWN, ord('j') ):
                self.isel += 1
            elif ch in ( c.KEY_UP, ord('k') ):
                self.isel = max( 0, self.isel - 1 )
            elif ch in ( c.KEY_NPAGE, ord(' ') ):
                self.isel += height - 1
            elif ch == c.KEY_PPAGE:
                self.isel = max( 0, self.isel - height + 1 )
            elif ch == c.KEY_HOME:
                self.isel = 0
            elif ch == c.KEY_END:
                self.isel = len( self.rows() )
            elif ch == ord('s'):
                name = sel.name if sel else None
                self.sort = _sort_orders[ ( _sort_orders.index( self.sort ) + 1 )
                                          % len(_sort_orders) ]
                if name:
                    self.select_name( name )
            elif ch == ord('f'):
                name = sel.name if sel else None
                self.failedonly = not self.failedonly
                if name:
                    self.select_name( name )
            elif ch == ord('?'):
                self.show_help( 'Keys in sb --testreport', _keyhelp )
                self.repaint_fully()
            elif ch == ord('e'):
                self.show_build_log( self.build_log_path(), failed = False )
            elif sel is None:
                continue
            elif ch in ( 10, 13, c.KEY_ENTER ):
                self.inspect( sel )
            elif ch == ord('o'):
                self.show_output( sel )
            elif ch in ( ord('r'), ord('b') ) and run and run.active:
                self.message = 'Please wait for the running tests to finish (or press c)'
            elif ch == ord('r'):
                self.rerun( sel, rebuild = False )
            elif ch == ord('b'):
                self.rerun( sel, rebuild = True )

class TestOutputView( OutputView ):

    """View of the output of a test, from which the test can also be run
    again (in the background, with the output being updated as it appears)."""

    statusbar = ( 'Esc:back  q:quit  r:rerun  b:rebuild+rerun  arrows, j k h l:scroll'
                  '  PgUp/PgDn  Home/End' )

    def __init__( self, ui, name ):
        import os
        self.ui = ui
        self.name = name
        self._was_running = False
        super().__init__( ui.scr, '', os.path.join( ui.report.testdir, name, 'output.log' ) )
        self._update_title()

    def _status( self ):
        run = self.ui.report.run
        if run and run.active and self.name in run.names:
            st = run.status( self.name )
            if st != 'done':
                return st
        return None

    def _update_title( self ):
        st = self._status()
        if st == 'running':
            self.title = f'Output of {self.name} (running...)'
        elif st == 'waiting':
            self.title = f'Output of {self.name} (waiting to run...)'
        else:
            r = next( ( e for e in self.ui.all_results if e.name == self.name ), None )
            if r is None or r.ec is None:
                ecstr = 'killed or interrupted'
            else:
                ecstr = f'exit code {r.ec}'
                if r.ec == 0 and r.logdiff_failed:
                    ecstr += ', differs from the reference log'
            self.title = f'Output of {self.name} ({ecstr})'

    def tick_ms( self ):
        run = self.ui.report.run
        return 500 if ( run and run.active ) else -1

    def on_tick( self ):
        run = self.ui.report.run
        if run and not run.poll() and self._was_running:
            self._was_running = False
            self.ui._load()
            r = next( ( e for e in self.ui.all_results if e.name == self.name ), None )
            self.message = f'{self.name} now ' + ( 'FAILS' if ( r is None or r.failed )
                                                    else 'passes' )
        self._update_title()

    def on_key( self, ch ):
        if ch not in ( ord('r'), ord('b') ):
            return False
        ui = self.ui
        run = ui.report.run
        if run and run.active:
            self.message = 'Please wait for the running tests to finish'
            return True
        if ch == ord('b'):
            def do_rebuild():
                print(f'Rebuilding before running {self.name} again...', flush = True)
                return ui.report.rebuild_fct()
            ok = self.run_outside_curses( do_rebuild )
            self.repaint_fully()
            if not ok:
                self.show_build_log( ui.build_log_path(), failed = True )
                self.message = 'Build failed'
                return True
        ui.start_tests( [ self.name ] )
        run = ui.report.run
        if not ( run and run.active ):
            self.message = ui.message
            return True
        self._was_running = True
        self.y = 0
        self.message = f'Running {self.name} again...'
        self._update_title()
        return True

class InteractiveReport:

    """Settings and shared state of an interactive test report session."""

    def __init__( self, testdir, installdir, spec, filters, warning,
                  rerun_fct, rebuild_fct, run = None, start_run_fct = None ):
        self.testdir = testdir
        self.installdir = installdir
        self.spec = spec
        self.filters = filters
        self.warning = warning
        self.rerun_fct = rerun_fct
        self.rebuild_fct = rebuild_fct
        #Tests running in the background (BackgroundTestRun object), and a
        #function starting a new run of the given tests:
        self.run = run
        self.initial_run = run
        self.start_run_fct = start_run_fct
        self.stop_on_quit = True
        self.code_required = True
        self.updated_files = []

def run_interactive_report( report ):
    """Run the interactive user interface. Returns when the user quits."""
    run_curses_app( lambda stdscr : TestReportUI( stdscr, report ).run() )
