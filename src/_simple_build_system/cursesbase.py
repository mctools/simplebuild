# Common functionality for the curses based user interfaces (see reflogui.py
# and testreportui.py).

def relpath( path ):
    import os
    try:
        return os.path.relpath( path )
    except ValueError:
        return str(path)

def run_curses_app( fct ):
    """Run fct(stdscr) in a curses session (restoring the terminal afterwards,
    also in case of exceptions)."""
    import os
    import curses
    import locale
    locale.setlocale( locale.LC_ALL, '' )
    os.environ.setdefault( 'ESCDELAY', '25' )
    return curses.wrapper( fct )

class ScreenBase:

    """Base class for curses based screens, with helpers for drawing text with
    the styles of diffrender.py (and a few more), and for asking for input."""

    def __init__( self, stdscr ):
        import curses
        import locale
        self.curses = curses
        self.scr = stdscr
        self.message = ''
        enc = locale.getpreferredencoding( False ) or 'ascii'
        self._encoding = enc if enc.lower().replace('-','') == 'utf8' else 'ascii'
        self._init_attrs()

    def _init_attrs( self ):
        c = self.curses
        a = dict( ctx = c.A_NORMAL, del_ = c.A_NORMAL, ins = c.A_NORMAL,
                  delhl = c.A_REVERSE | c.A_BOLD, inshl = c.A_REVERSE | c.A_UNDERLINE,
                  meta = c.A_BOLD, dim = c.A_DIM, title = c.A_REVERSE,
                  gutter = c.A_BOLD, ok = c.A_NORMAL, bad = c.A_BOLD,
                  selected = c.A_REVERSE )
        if c.has_colors():
            c.start_color()
            try:
                c.use_default_colors()
                bg = -1
            except c.error:
                bg = c.COLOR_BLACK
            pairs = [ ( 'del_', c.COLOR_RED, bg, 0 ),
                      ( 'ins', c.COLOR_GREEN, bg, 0 ),
                      ( 'delhl', c.COLOR_WHITE, c.COLOR_RED, c.A_BOLD ),
                      ( 'inshl', c.COLOR_BLACK, c.COLOR_GREEN, 0 ),
                      ( 'meta', c.COLOR_CYAN, bg, 0 ),
                      ( 'title', c.COLOR_BLACK, c.COLOR_CYAN, 0 ),
                      ( 'gutter', c.COLOR_YELLOW, bg, c.A_BOLD ),
                      ( 'ok', c.COLOR_GREEN, bg, 0 ),
                      ( 'bad', c.COLOR_RED, bg, c.A_BOLD ) ]
            for i, ( name, fg, bgc, extra ) in enumerate( pairs ):
                try:
                    c.init_pair( i + 1, fg, bgc )
                    a[name] = c.color_pair( i + 1 ) | extra
                except c.error:
                    pass
        a['del'] = a.pop('del_')
        self.attrs = a

    def _text( self, s ):
        if self._encoding == 'ascii':
            return s.encode( 'ascii', errors = 'replace' ).decode( 'ascii' )
        return s

    def _put( self, y, x, text, attr = 0 ):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w - 1:
            return
        text = self._text( text )[:max(0, w - 1 - x)]
        try:
            self.scr.addstr( y, x, text, attr )
        except self.curses.error:
            pass

    def _put_segments( self, y, x, segs, width ):
        for text, style in segs:
            if width <= 0:
                break
            text = text[:width]
            self._put( y, x, text, self.attrs[style] )
            x += len(text)
            width -= len(text)

    def draw( self ):
        raise NotImplementedError

    def prompt( self, text ):
        """Ask for input on the message line. Returns None if cancelled."""
        c = self.curses
        typed = ''
        try:
            c.curs_set(1)
        except c.error:
            pass
        try:
            while True:
                self.message = ''
                self.draw()
                h, w = self.scr.getmaxyx()
                self._put( h - 2, 0, ( text + typed ).ljust( w - 1 ), self.attrs['meta'] )
                self.scr.move( h - 2, min( w - 2, len(text) + len(typed) ) )
                ch = self.scr.getch()
                if ch in ( 10, 13, c.KEY_ENTER ):
                    return typed
                if ch == 27:
                    return None
                if ch in ( c.KEY_BACKSPACE, 127, 8 ):
                    typed = typed[:-1]
                elif 32 <= ch < 127:
                    typed += chr(ch)
        finally:
            self.hide_cursor()

    def repaint_fully( self ):
        """Make sure the whole screen is redrawn next time (used when switching
        between screens)."""
        self.scr.clear()

    def hide_cursor( self ):
        try:
            self.curses.curs_set(0)
        except self.curses.error:
            pass

    def show_help( self, title, keyhelp ):
        self.scr.erase()
        self._put( 0, 0, f' {title} '.ljust( self.scr.getmaxyx()[1] ),
                   self.attrs['title'] )
        for i, ( k, d ) in enumerate( keyhelp ):
            self._put( i + 2, 2, k.ljust( 18 ), self.attrs['meta'] )
            self._put( i + 2, 21, d )
        self._put( len(keyhelp) + 3, 2, 'Press any key to return.', self.attrs['dim'] )
        self.scr.refresh()
        self.scr.getch()

    def run_outside_curses( self, fct ):
        """Temporarily leave curses mode (e.g. to show output of a build in the
        terminal), and call fct()."""
        c = self.curses
        c.def_prog_mode()
        c.endwin()
        try:
            return fct()
        finally:
            c.reset_prog_mode()
            self.scr.refresh()
