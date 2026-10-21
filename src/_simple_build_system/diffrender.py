# Rendering of differences between two files (e.g. a reference log and the
# output of a test), for display in terminals.
#
# The differences are rendered as rows of segments, where each segment is a
# (text,style) tuple. This allows the same rendering to be used for both plain
# terminal output (see segments_to_text) and curses based interfaces. Changed
# words within changed lines are highlighted, and changed whitespace is made
# visible (it is highlighted like other changes, tabs are shown as "→", and
# other control characters such as carriage returns as e.g. "␍").
#
# Styles:
#
#   'ctx'   : unchanged text.
#   'del'   : text of a removed line.
#   'ins'   : text of an added line.
#   'delhl' : changed part of a removed line.
#   'inshl' : changed part of an added line.
#   'meta'  : headers, notes, and markers (e.g. missing newline at end of file).
#   'dim'   : line numbers and other less important information.

import re
import difflib

_re_tokens = re.compile(r'\s+|\w+|[^\w\s]')

#Lines are only highlighted word by word if they are at least this similar
#(otherwise the highlighting is mostly noise):
_min_similarity_for_word_highlights = 0.4

no_newline_note = '\\ No newline at end of file'

def visible_text( text ):
    """Text of (part of) a line, with tabs and other control characters
    replaced by visible symbols (each still taking up a single column)."""
    res = []
    for c in text:
        o = ord(c)
        if c == '\t':
            res.append('→')
        elif o < 32:
            res.append(chr(0x2400+o))#control pictures, e.g. ␍
        elif o == 127:
            res.append('␡')
        elif 0xdc80 <= o <= 0xdcff:
            res.append('�')#undecodable byte (surrogate escape)
        else:
            res.append(c)
    return ''.join(res)

def _split_eol( line ):
    if line.endswith('\n'):
        return line[:-1], True
    return line, False

def _line_segments( line, style ):
    text, has_eol = _split_eol( line )
    segs = [ ( visible_text(text), style ) ] if text else []
    if not has_eol:
        segs.append( ( ' ' + no_newline_note, 'meta' ) )
    return segs

def _merge( segs ):
    res = []
    for text, style in segs:
        if not text:
            continue
        if res and res[-1][1] == style:
            res[-1] = ( res[-1][0] + text, style )
        else:
            res.append( ( text, style ) )
    return res

def _paired_line_segments( line_a, line_b ):
    """Segments for a removed line and the added line replacing it, with the
    changed words highlighted. Returns None if the lines are too different
    for such highlighting to be useful."""
    text_a, eol_a = _split_eol( line_a )
    text_b, eol_b = _split_eol( line_b )
    ta, tb = _re_tokens.findall( text_a ), _re_tokens.findall( text_b )
    sm = difflib.SequenceMatcher( None, ta, tb, autojunk = False )
    if ( ta or tb ) and sm.ratio() < _min_similarity_for_word_highlights:
        return None
    segs_a, segs_b = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        sa = visible_text( ''.join( ta[i1:i2] ) )
        sb = visible_text( ''.join( tb[j1:j2] ) )
        if tag == 'equal':
            segs_a.append( ( sa, 'del' ) )
            segs_b.append( ( sb, 'ins' ) )
        else:
            segs_a.append( ( sa, 'delhl' ) )
            segs_b.append( ( sb, 'inshl' ) )
    if not eol_a:
        segs_a.append( ( ' ' + no_newline_note, 'meta' ) )
    if not eol_b:
        segs_b.append( ( ' ' + no_newline_note, 'meta' ) )
    return _merge( segs_a ), _merge( segs_b )

def _replace_block_segments( lines_a, lines_b ):
    """Segments for a block of removed lines and the block of added lines
    replacing them. Lines are paired up in order for word highlighting.
    Returns (list_of_segs_a, list_of_segs_b)."""
    res_a, res_b = [], []
    for i in range( max( len(lines_a), len(lines_b) ) ):
        la = lines_a[i] if i < len(lines_a) else None
        lb = lines_b[i] if i < len(lines_b) else None
        p = _paired_line_segments( la, lb ) if ( la is not None
                                                 and lb is not None ) else None
        if p:
            res_a.append( p[0] )
            res_b.append( p[1] )
            continue
        if la is not None:
            res_a.append( _line_segments( la, 'del' ) )
        if lb is not None:
            res_b.append( _line_segments( lb, 'ins' ) )
    return res_a, res_b

def changes_rows( lines_a, lines_b, context = 3, note = None ):
    """Rows (lists of segments) showing the changed lines in a format similar
    to the unified diff format, with context lines around them. If note is
    given, it is added as a first row."""
    rows = []
    if note:
        rows.append( [ ( note, 'meta' ) ] )
    sm = difflib.SequenceMatcher( None, lines_a, lines_b, autojunk = False )
    for group in sm.get_grouped_opcodes( context ):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        rows.append( [ ( '@@ -%i,%i +%i,%i @@'%( i1+1, i2-i1, j1+1, j2-j1 ),
                         'meta' ) ] )
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in lines_a[i1:i2]:
                    rows.append( [ ( ' ', 'ctx' ) ]
                                 + _line_segments( line, 'ctx' ) )
                continue
            segs_a, segs_b = _replace_block_segments( lines_a[i1:i2],
                                                      lines_b[j1:j2] )
            rows += [ [ ( '-', 'del' ) ] + s for s in segs_a ]
            rows += [ [ ( '+', 'ins' ) ] + s for s in segs_b ]
    return rows

class SideBySideRow:

    """Row in a side-by-side view. The kind is one of 'equal', 'changed',
    'removed', 'added', or 'skipped' (the latter represents a number of
    identical lines which are not shown, in which case nskipped is set). For
    each side, the line number (counting from 1) and the segments are given (or
    None if there is no line on that side)."""

    def __init__( self, kind, lno_a = None, segs_a = None,
                  lno_b = None, segs_b = None, nskipped = 0 ):
        self.kind = kind
        self.lno_a, self.segs_a = lno_a, segs_a
        self.lno_b, self.segs_b = lno_b, segs_b
        self.nskipped = nskipped

    @property
    def is_change( self ):
        return self.kind in ( 'changed', 'removed', 'added' )

    gutter_symbols = { 'equal' : ' ', 'changed' : '|', 'removed' : '<',
                       'added' : '>', 'skipped' : ' ' }

    @property
    def gutter( self ):
        return self.gutter_symbols[self.kind]

def sidebyside_rows( lines_a, lines_b, context = None ):
    """Rows (SideBySideRow objects) showing both files side by side. If context
    is not None, runs of identical lines are only shown up to that many lines
    away from changes."""
    rows = []
    sm = difflib.SequenceMatcher( None, lines_a, lines_b, autojunk = False )
    opcodes = sm.get_opcodes()
    for iop, ( tag, i1, i2, j1, j2 ) in enumerate( opcodes ):
        if tag == 'equal':
            n = i2 - i1
            show = list( range( n ) )
            if context is not None:
                first = iop == 0
                last = iop == len(opcodes) - 1
                keep_head = 0 if first else context
                keep_tail = 0 if last else context
                if n > keep_head + keep_tail + 1:
                    show = ( list( range( keep_head ) ) + [ None ]
                             + list( range( n - keep_tail, n ) ) )
            for k in show:
                if k is None:
                    rows.append( SideBySideRow( 'skipped',
                                                nskipped = n - keep_head - keep_tail ) )
                    continue
                rows.append( SideBySideRow( 'equal',
                                            i1+k+1, _line_segments( lines_a[i1+k], 'ctx' ),
                                            j1+k+1, _line_segments( lines_b[j1+k], 'ctx' ) ) )
            continue
        segs_a, segs_b = _replace_block_segments( lines_a[i1:i2], lines_b[j1:j2] )
        for k in range( max( len(segs_a), len(segs_b) ) ):
            sa = segs_a[k] if k < len(segs_a) else None
            sb = segs_b[k] if k < len(segs_b) else None
            kind = 'changed' if ( sa is not None and sb is not None ) else (
                'removed' if sa is not None else 'added' )
            rows.append( SideBySideRow( kind,
                                        i1+k+1 if sa is not None else None, sa,
                                        j1+k+1 if sb is not None else None, sb ) )
    return rows

def segments_length( segs ):
    return sum( len(text) for text, _ in segs )

def clip_segments( segs, offset, width ):
    """Return the part of the segments which is visible when skipping the
    first offset columns, and showing at most width columns."""
    res = []
    pos = 0
    for text, style in segs:
        a, b = pos, pos + len(text)
        pos = b
        lo, hi = max( a, offset ), min( b, offset + width )
        if lo < hi:
            res.append( ( text[lo-a:hi-a], style ) )
    return res

_ansi_styles = { 'ctx' : '', 'del' : '\033[31m', 'ins' : '\033[32m',
                 'delhl' : '\033[97;41m', 'inshl' : '\033[30;42m',
                 'meta' : '\033[36m', 'dim' : '\033[90m' }

#Markers used for highlighted segments when colours are not available (similar
#to the output of the wdiff command):
_plain_markers = { 'delhl' : ( '[-', '-]' ), 'inshl' : ( '{+', '+}' ) }

def segments_to_text( segs, color ):
    """Convert segments to a string, using ANSI escape codes for the styles if
    color is True, and otherwise markers around highlighted segments."""
    res = []
    for text, style in segs:
        if color:
            code = _ansi_styles[style]
            res.append( f'{code}{text}\033[0m' if code else text )
        else:
            m = _plain_markers.get( style )
            res.append( f'{m[0]}{text}{m[1]}' if m else text )
    return ''.join(res)
