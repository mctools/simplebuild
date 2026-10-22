import pytest

from _simple_build_system import diffrender as dr

pytestmark = pytest.mark.unit

def lines( s ):
    return s.splitlines( True )

def text( rows ):
    return [ dr.segments_to_text( r, color = False ) for r in rows ]

def test_visible_text():
    assert dr.visible_text( 'a\tb\rc\x00d\x7f' ) == 'a→b␍c␀d␡'
    assert dr.visible_text( 'x\udcffy' ) == 'x�y'
    assert dr.visible_text( 'æøå 1 2' ) == 'æøå 1 2'

def test_changes_rows():
    rows = dr.changes_rows( lines( 'a\nx = 12\nvalue 3\nb\nc\nd\ne\nf\ng\n' ),
                            lines( 'a\nx = 1 2  \nvalue\t3\nb\nc\nd\ne\nf\ng' ),
                            context = 1, note = 'NOTE' )
    assert text( rows ) == [ 'NOTE',
                             '@@ -1,4 +1,4 @@',
                             ' a',
                             '-x = [-12-]',
                             '-value[- -]3',
                             '+x = {+1 2  +}',
                             '+value{+→+}3',
                             ' b',
                             '@@ -8,2 +8,2 @@',
                             ' f',
                             '-g',
                             '+g \\ No newline at end of file' ]
    #Styles of an added line with a highlighted word:
    assert rows[5] == [ ( '+', 'ins' ), ( 'x = ', 'ins' ), ( '1 2  ', 'inshl' ) ]

def test_changes_rows_dissimilar_lines_not_word_highlighted():
    rows = dr.changes_rows( lines( 'completely different\n' ),
                            lines( 'nothing in common at all\n' ) )
    assert text( rows )[1:] == [ '-completely different',
                                 '+nothing in common at all' ]

def test_changes_rows_identical():
    assert dr.changes_rows( lines('a\nb\n'), lines('a\nb\n') ) == []

def test_sidebyside_rows():
    a = lines( ''.join( f'l{i}\n' for i in range(20) ) )
    b = a[:5] + [ 'l5 x\n' ] + a[6:15] + a[16:] + [ 'extra\n' ]
    rows = dr.sidebyside_rows( a, b )
    assert len(rows) == 21
    assert [ r.kind for r in rows if r.kind != 'equal' ] == [ 'changed', 'removed', 'added' ]
    r = rows[5]
    assert ( r.lno_a, r.lno_b, r.gutter ) == ( 6, 6, '|' )
    assert r.segs_a == [ ( 'l5', 'del' ) ]
    assert r.segs_b == [ ( 'l5', 'ins' ), ( ' x', 'inshl' ) ]
    r = rows[15]
    assert ( r.kind, r.lno_a, r.lno_b, r.segs_b, r.gutter ) == ( 'removed', 16, None, None, '<' )
    r = rows[-1]
    assert ( r.kind, r.lno_a, r.lno_b, r.gutter ) == ( 'added', None, 20, '>' )
    #With context, long runs of identical lines are skipped:
    rows = dr.sidebyside_rows( a, b, context = 2 )
    assert [ ( r.kind, r.nskipped, r.lno_a, r.lno_b ) for r in rows ] == [
        ( 'skipped', 3, None, None ),
        ( 'equal', 0, 4, 4 ), ( 'equal', 0, 5, 5 ),
        ( 'changed', 0, 6, 6 ),
        ( 'equal', 0, 7, 7 ), ( 'equal', 0, 8, 8 ),
        ( 'skipped', 5, None, None ),
        ( 'equal', 0, 14, 14 ), ( 'equal', 0, 15, 15 ),
        ( 'removed', 0, 16, None ),
        #Short runs of identical lines between changes are not skipped:
        ( 'equal', 0, 17, 16 ), ( 'equal', 0, 18, 17 ),
        ( 'equal', 0, 19, 18 ), ( 'equal', 0, 20, 19 ),
        ( 'added', 0, None, 20 ) ]

def test_clip_segments():
    segs = [ ( 'abc', 'del' ), ( 'def', 'delhl' ), ( 'gh', 'del' ) ]
    assert dr.segments_length( segs ) == 8
    assert dr.clip_segments( segs, 0, 100 ) == segs
    assert dr.clip_segments( segs, 2, 3 ) == [ ( 'c', 'del' ), ( 'de', 'delhl' ) ]
    assert dr.clip_segments( segs, 7, 5 ) == [ ( 'h', 'del' ) ]
    assert dr.clip_segments( segs, 8, 5 ) == []

def test_segments_to_text_color():
    s = dr.segments_to_text( [ ( 'a', 'ctx' ), ( 'b', 'inshl' ) ], color = True )
    assert s == 'a\033[30;42mb\033[0m'

def test_format_duration():
    from _simple_build_system.testreportui import format_duration
    assert format_duration( 0.2 ) == '0s'
    assert format_duration( 59.4 ) == '59s'
    assert format_duration( 61 ) == '1m01s'
    assert format_duration( 3725 ) == '1h02m'
