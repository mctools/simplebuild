# Curses based user interface for "sb --reflogupdate" (the logic is in
# reflogupdate.py, and the rendering of differences in diffrender.py).

from . import diffrender
from .cursesbase import ( ScreenBase, relpath as _relpath, run_curses_app,
                          QuitApp, is_back_key )

_views = ( ( 'sbs', 'side by side' ),
           ( 'sbs3', 'side by side, changes only' ),
           ( 'changes', 'changed lines' ) )

_keyhelp = [
    ( 'q', 'Quit' ),
    ( 'Esc', 'Go back (when opened from another screen)' ),
    ( '+ / -', 'Next / previous test' ),
    ( 'n / p', 'Next / previous difference' ),
    ( 'v', 'Change view (side by side, side by side with changes only, changed lines)' ),
    ( 'arrows, j k h l', 'Scroll (also PgUp/PgDn/Space and Home/End)' ),
    ( 'u', 'Update the reference log in the package with the output of the test' ),
    ( 'x', 'Stop requiring codes for updates for the rest of this session' ),
    ( 'o', 'Show the complete output of the test' ),
    ( 'r', 'Run the test again' ),
    ( 'b', 'Rebuild (as with "sb"), and run the test again' ),
    ( 'e', 'Show the output of the last rebuild (e.g. compilation errors)' ),
    ( '?', 'Show this help' ),
    ( '', 'Letter keys work the same independently of Shift and Caps Lock.' ),
]

_statusbar = ( 'q:quit  +/-:test  n/p:diff  v:view  u:update  x:no codes'
               '  o:output  r:rerun  b:rebuild+rerun  e:build log  ?:help' )


class ReflogUI( ScreenBase ):

    def __init__( self, stdscr, session, title = 'sb --reflogupdate',
                  toplevel = True ):
        super().__init__( stdscr )
        self.toplevel = toplevel
        self.session = session
        self.title = title
        self.icand = 0
        self.iview = 0
        self.y = 0
        self.x = 0
        self._rows_cache = {}

    #Helpers:

    @property
    def cand( self ):
        return self.session.candidates[self.icand]

    def rows( self ):
        c = self.cand
        key = ( id(c), self.iview, c.updated, c.job_failed )
        if self._rows_cache.get('key') != key or self._rows_cache.get('lines') is not c.lines():
            ll = c.lines()
            view = _views[self.iview][0]
            if ll is None:
                rows = []
            elif view == 'changes':
                rows = diffrender.changes_rows( ll[0], ll[1] )
            else:
                rows = diffrender.sidebyside_rows( ll[0], ll[1],
                                                   context = 3 if view == 'sbs3' else None )
            self._rows_cache = dict( key = key, lines = ll, rows = rows )
        return self._rows_cache['rows']

    def _row_is_change_start( self, row ):
        if isinstance( row, diffrender.SideBySideRow ):
            return row.is_change
        return bool(row) and row[0][1] == 'meta' and row[0][0].startswith('@@')

    #Drawing:

    def body_geometry( self ):
        h, w = self.scr.getmaxyx()
        top = 4
        return top, max( 1, h - top - 2 ), w

    def draw( self ):
        from .reflogdiff import differs_only_in_whitespace
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        s = self.session
        c = self.cand
        status = ( 'UPDATED' if c.updated else
                   ( 'TEST FAILED' if c.job_failed else
                     ( 'IDENTICAL' if c.identical else 'DIFFERS' ) ) )
        title = ' %s   [%i/%i] %s (%s)   %s'%( self.title, self.icand + 1,
                                                              len(s.candidates),
                                                              c.name, c.pkgname, status )
        right = 'view: %s '%_views[self.iview][1]
        self._put( 0, 0, title.ljust( w ), self.attrs['title'] )
        self._put( 0, max( len(title) + 2, w - 1 - len(right) ), right, self.attrs['title'] )
        shown, _ = c.source_reflog()
        self._put( 1, 0, 'Reference log in package: %s'%_relpath(shown),
                   self.attrs['dim'] )
        ll = c.lines()
        if ll is not None and not c.identical and differs_only_in_whitespace( *ll ):
            from .reflogdiff import whitespace_only_note
            self._put( 2, 0, whitespace_only_note, self.attrs['meta'] )
        elif not s.code_required:
            self._put( 2, 0, 'Codes are not required for updates in this session',
                       self.attrs['dim'] )
        top, height, width = self.body_geometry()
        if _views[self.iview][0] == 'changes':
            self._put( 3, 0, '--- reference log', self.attrs['del'] )
            self._put( 3, 20, '+++ test output', self.attrs['ins'] )
        else:
            half = ( width - 3 ) // 2
            self._put( 3, 0, 'Reference log'.center( half ), self.attrs['del'] )
            self._put( 3, half + 3, 'Test output'.center( half ), self.attrs['ins'] )
        rows = self.rows()
        self.y = max( 0, min( self.y, max( 0, len(rows) - height ) ) )
        if ll is None:
            self._put( top, 0, 'Could not read the reference log or the output of the test' )
        elif not rows:
            self._put( top, 0, 'The output of the test is identical to the reference log.' )
        for i, row in enumerate( rows[self.y:self.y+height] ):
            if isinstance( row, diffrender.SideBySideRow ):
                self._draw_sbs_row( top + i, row, width )
            else:
                self._put_segments( top + i, 0,
                                    diffrender.clip_segments( row, self.x, width - 1 ),
                                    width - 1 )
        self._put( h - 2, 0, self.message, self.attrs['meta'] )
        self._put( h - 1, 0, _statusbar.ljust( w ), self.attrs['title'] )
        self.scr.refresh()

    def _draw_sbs_row( self, y, row, width ):
        ll = self.cand.lines()
        nlno = len( str( max( len(ll[0]), len(ll[1]), 1 ) ) ) if ll else 1
        half = ( width - 3 ) // 2
        textw = max( 1, half - nlno - 1 )
        if row.kind == 'skipped':
            self._put( y, 0, ( ' ⋯ %i identical lines ⋯ '%row.nskipped ).center( width - 1 ),
                       self.attrs['dim'] )
            return
        for side, x0 in ( ( 'a', 0 ), ( 'b', half + 3 ) ):
            lno = getattr( row, 'lno_'+side )
            segs = getattr( row, 'segs_'+side )
            if lno is None:
                continue
            self._put( y, x0, str(lno).rjust( nlno ), self.attrs['dim'] )
            self._put_segments( y, x0 + nlno + 1,
                                diffrender.clip_segments( segs, self.x, textw ), textw )
        self._put( y, half + 1, row.gutter, self.attrs['gutter'] )

    #Input:

    def confirm_with_code( self, what ):
        code = self.session.new_code()
        typed = self.prompt( f'To {what}, type the code {code} in reverse'
                             ' order (ESC cancels): ' )
        if typed is None:
            self.message = 'Cancelled'
            return False
        if not self.session.code_matches( code, typed ):
            self.message = 'Wrong code, nothing was done'
            return False
        return True

    def goto_candidate( self, i ):
        self.icand = i % len( self.session.candidates )
        self.y = self.x = 0

    def do_update( self ):
        c = self.cand
        if c.job_failed:
            self.message = 'The reference log can not be updated, since the test failed'
            return
        if c.identical:
            self.message = 'Nothing to update, the output is identical to the reference log'
            return
        if self.session.code_required:
            if not self.confirm_with_code( 'update' ):
                return
        shown = self.session.update( c )
        self.message = f'Updated {_relpath(shown)}'
        pending = [ i for i, cc in enumerate( self.session.candidates )
                    if not cc.updated and not cc.identical ]
        later = [ i for i in pending if i > self.icand ] or pending
        if later:
            self.goto_candidate( later[0] )
        else:
            self.message += ' (no more reference logs to update, press q to quit)'

    def do_unlock( self ):
        if not self.session.code_required:
            self.message = 'Codes are already not required in this session'
            return
        if self.confirm_with_code( 'stop requiring codes' ):
            self.session.disable_code_requirement()
            self.message = 'Codes are no longer required for updates in this session'

    def do_rerun( self, rebuild ):
        c = self.cand
        if rebuild:
            def rebuild_and_rerun():
                print(f'Rebuilding before running {c.name} again...', flush = True)
                return self.session.rerun( c, rebuild = True )
            ok, msg = self.run_outside_curses( rebuild_and_rerun )
            if not ok and msg == 'Build failed':
                self.show_build_log( self.build_log_path(), failed = True )
        else:
            self.message = f'Running {c.name} again...'
            self.draw()
            ok, msg = self.session.rerun( c )
        self.message = msg
        self._rows_cache = {}

    def build_log_path( self ):
        return getattr( self.session.rebuild_fct, 'log_path', None )

    def show_output( self ):
        from .cursesbase import OutputView
        c = self.cand
        OutputView( self.scr, f'Output of {c.name}', c.output ).run()
        self.repaint_fully()

    def scroll( self, dy = 0, dx = 0 ):
        self.y = max( 0, self.y + dy )
        self.x = max( 0, self.x + dx )

    def next_diff( self, direction ):
        rows = self.rows()
        idx = range( self.y + 1, len(rows) ) if direction > 0 else range( self.y - 1, -1, -1 )
        for i in idx:
            if ( self._row_is_change_start( rows[i] )
                 and ( i == 0 or not self._row_is_change_start( rows[i-1] ) ) ):
                self.y = max( 0, i - 2 )
                return
        self.message = 'No more differences in this direction'

    def run( self ):
        c = self.curses
        self.hide_cursor()
        self.scr.keypad( True )
        self.repaint_fully()
        self.message = 'Press ? for help'
        while True:
            self.draw()
            ch = self.getkey()
            _, height, _ = self.body_geometry()
            self.message = ''
            if ch == ord('q'):
                raise QuitApp()
            elif is_back_key( ch ):
                if self.toplevel:
                    self.message = 'Press q to quit'
                else:
                    return
            elif ch in ( ord('+'), ord('=') ):
                self.goto_candidate( self.icand + 1 )
            elif ch in ( ord('-'), ord('_') ):
                self.goto_candidate( self.icand - 1 )
            elif ch == ord('n'):
                self.next_diff( +1 )
            elif ch == ord('p'):
                self.next_diff( -1 )
            elif ch == ord('v'):
                self.iview = ( self.iview + 1 ) % len(_views)
                self.y = 0
                self.repaint_fully()
            elif ch in ( c.KEY_DOWN, ord('j') ):
                self.scroll( dy = 1 )
            elif ch in ( c.KEY_UP, ord('k') ):
                self.scroll( dy = -1 )
            elif ch in ( c.KEY_NPAGE, ord(' ') ):
                self.scroll( dy = height - 1 )
            elif ch == c.KEY_PPAGE:
                self.scroll( dy = -( height - 1 ) )
            elif ch == c.KEY_HOME:
                self.y = 0
            elif ch == c.KEY_END:
                self.y = len( self.rows() )
            elif ch in ( c.KEY_RIGHT, ord('l') ):
                self.scroll( dx = 8 )
            elif ch in ( c.KEY_LEFT, ord('h') ):
                self.scroll( dx = -8 )
            elif ch == ord('u'):
                self.do_update()
            elif ch == ord('x'):
                self.do_unlock()
            elif ch == ord('o'):
                self.show_output()
            elif ch == ord('r'):
                self.do_rerun( rebuild = False )
            elif ch == ord('b'):
                self.do_rerun( rebuild = True )
            elif ch == ord('e'):
                self.show_build_log( self.build_log_path(), failed = False )
            elif ch == ord('?'):
                self.show_help( f'Keys in {self.title}', _keyhelp )
                self.repaint_fully()
            elif ch == c.KEY_RESIZE:
                pass

def run_reflogupdate( session ):
    """Run the interactive user interface. Returns when the user quits."""
    run_curses_app( lambda stdscr : ReflogUI( stdscr, session ).run() )
