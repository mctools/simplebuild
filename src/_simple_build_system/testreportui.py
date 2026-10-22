# Curses based interactive test report ("sb --testreport=interactive"),
# showing the results of the last test run in a table, from which the output
# of tests or differences with reference logs can be inspected, and tests can
# be run again.

from .cursesbase import ScreenBase, run_curses_app

_sort_orders = ( 'name', 'pkg', 'time' )

_keyhelp = [
    ( 'q', 'Quit' ),
    ( 'arrows, j k', 'Select test (also PgUp/PgDn/Space, Home/End or g/G)' ),
    ( 'Enter', 'Show differences with the reference log (if any), otherwise the output' ),
    ( 'o', 'Show the output of the test' ),
    ( 's', 'Change sort order (by name, by package, slowest first)' ),
    ( 'f', 'Show only failed tests, or all tests' ),
    ( 'r', 'Run the selected test again' ),
    ( 'R', 'Rebuild (as with "sb"), and run the selected test again' ),
    ( '?', 'Show this help' ),
]

_statusbar = ( 'q:quit  Enter:inspect  o:output  s:sort  f:failed only'
               '  r:rerun  R:rebuild+rerun  ?:help' )

class OutputView( ScreenBase ):

    """Scrollable view of a text file (e.g. the output of a test)."""

    def __init__( self, stdscr, title, path ):
        super().__init__( stdscr )
        from .reflogdiff import read_lines
        from .diffrender import visible_text
        self.title = title
        try:
            self.lines = [ visible_text( line.rstrip('\n') ) for line in read_lines( path ) ]
        except OSError:
            self.lines = None
        self.y = self.x = 0

    def draw( self ):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        self._put( 0, 0, f' {self.title}'.ljust( w ), self.attrs['title'] )
        height = max( 1, h - 3 )
        if self.lines is None:
            self._put( 1, 0, 'The output is not available.' )
            lines = []
        else:
            lines = self.lines
            if not lines:
                self._put( 1, 0, 'The output is empty.', self.attrs['dim'] )
        self.y = max( 0, min( self.y, max( 0, len(lines) - height ) ) )
        nlno = len( str( max( 1, len(lines) ) ) )
        for i, line in enumerate( lines[self.y:self.y+height] ):
            self._put( 1 + i, 0, str( self.y + i + 1 ).rjust( nlno ), self.attrs['dim'] )
            self._put( 1 + i, nlno + 1, line[self.x:] )
        self._put( h - 2, 0, self.message, self.attrs['meta'] )
        self._put( h - 1, 0, 'q:back  arrows, j k h l:scroll  g/G:top/bottom'.ljust( w ),
                   self.attrs['title'] )
        self.scr.refresh()

    def run( self ):
        c = self.curses
        self.repaint_fully()
        while True:
            self.draw()
            ch = self.scr.getch()
            height = max( 1, self.scr.getmaxyx()[0] - 3 )
            if ch in ( ord('q'), ord('Q'), 27, c.KEY_BACKSPACE, 127 ):
                self.repaint_fully()
                return
            elif ch in ( c.KEY_DOWN, ord('j') ):
                self.y += 1
            elif ch in ( c.KEY_UP, ord('k') ):
                self.y = max( 0, self.y - 1 )
            elif ch in ( c.KEY_NPAGE, ord(' ') ):
                self.y += height - 1
            elif ch in ( c.KEY_PPAGE, ord('b') ):
                self.y = max( 0, self.y - height + 1 )
            elif ch in ( c.KEY_HOME, ord('g') ):
                self.y = 0
            elif ch in ( c.KEY_END, ord('G') ):
                self.y = len( self.lines or [] )
            elif ch in ( c.KEY_RIGHT, ord('l') ):
                self.x += 8
            elif ch in ( c.KEY_LEFT, ord('h') ):
                self.x = max( 0, self.x - 8 )

class TestReportUI( ScreenBase ):

    def __init__( self, stdscr, report ):
        super().__init__( stdscr )
        self.report = report
        self.sort = report.spec['sort']
        self.failedonly = report.spec['failedonly']
        self.isel = 0
        self.ytop = 0
        self._load()

    def _load( self ):
        from .testlauncher import load_results, make_filter_fct
        self.runinfo, results = load_results( self.report.testdir )
        filter_fct = make_filter_fct( self.report.filters )
        self.all_results = [ r for r in ( results or [] ) if filter_fct( r.name ) ]

    def rows( self ):
        rr = [ r for r in self.all_results if r.failed or not self.failedonly ]
        if self.sort == 'pkg':
            rr.sort( key = lambda r : ( r.pkgname or '', r.name ) )
        elif self.sort == 'time':
            rr.sort( key = lambda r : ( -r.time_ms, r.name ) )
        return rr

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
        nfailed = sum( 1 for r in self.all_results if r.failed )
        title = ' sb --testreport   %i tests, %i failed   sort: %s%s'%(
            len(self.all_results), nfailed, self.sort,
            '   (only failed tests shown)' if self.failedonly else '' )
        self._put( 0, 0, title.ljust( w ), self.attrs['title'] )
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
        for i, r in enumerate( rows[self.ytop:self.ytop+height] ):
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
        import os
        ecstr = 'killed or interrupted' if r.ec is None else f'exit code {r.ec}'
        OutputView( self.scr, f'Output of {r.name} ({ecstr})',
                    os.path.join( self.report.testdir, r.name, 'output.log' ) ).run()

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
        ReflogUI( self.scr, session, title = 'sb --testreport' ).run()
        self.repaint_fully()
        rep.code_required = session.code_required
        for f in session.updated_files:
            if f not in rep.updated_files:
                rep.updated_files.append( f )
        self._load()
        self.select_name( r.name )

    def rerun( self, r, rebuild ):
        from .reflogui import wait_for_enter_after_failed_build
        rep = self.report
        if rebuild:
            def do_rebuild():
                print(f'Rebuilding before running {r.name} again...', flush = True)
                ok = rep.rebuild_fct()
                if not ok:
                    wait_for_enter_after_failed_build()
                return ok
            if not self.run_outside_curses( do_rebuild ):
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
        c = self.curses
        self.hide_cursor()
        self.scr.keypad( True )
        self.message = 'Press ? for help'
        while True:
            self.draw()
            ch = self.scr.getch()
            _, height, _ = self.body_geometry()
            self.message = ''
            sel = self.selected
            if ch in ( ord('q'), ord('Q') ):
                return
            elif ch in ( c.KEY_DOWN, ord('j') ):
                self.isel += 1
            elif ch in ( c.KEY_UP, ord('k') ):
                self.isel = max( 0, self.isel - 1 )
            elif ch in ( c.KEY_NPAGE, ord(' ') ):
                self.isel += height - 1
            elif ch in ( c.KEY_PPAGE, ord('b') ):
                self.isel = max( 0, self.isel - height + 1 )
            elif ch in ( c.KEY_HOME, ord('g') ):
                self.isel = 0
            elif ch in ( c.KEY_END, ord('G') ):
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
            elif sel is None:
                continue
            elif ch in ( 10, 13, c.KEY_ENTER ):
                self.inspect( sel )
            elif ch == ord('o'):
                self.show_output( sel )
            elif ch == ord('r'):
                self.rerun( sel, rebuild = False )
            elif ch == ord('R'):
                self.rerun( sel, rebuild = True )

class InteractiveReport:

    """Settings and shared state of an interactive test report session."""

    def __init__( self, testdir, installdir, spec, filters, warning,
                  rerun_fct, rebuild_fct ):
        self.testdir = testdir
        self.installdir = installdir
        self.spec = spec
        self.filters = filters
        self.warning = warning
        self.rerun_fct = rerun_fct
        self.rebuild_fct = rebuild_fct
        self.code_required = True
        self.updated_files = []

def run_interactive_report( report ):
    """Run the interactive user interface. Returns when the user quits."""
    run_curses_app( lambda stdscr : TestReportUI( stdscr, report ).run() )
