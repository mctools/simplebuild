import pytest

from _simple_build_system import reflogdiff

pytestmark = pytest.mark.unit

def lines( s ):
    return s.splitlines( True )

def test_identical():
    assert reflogdiff.unified_diff_text( lines('a\nb\n'), lines('a\nb\n') ) == ''

@pytest.mark.parametrize( 'ref,out', [
    ( 'a\nb\n', 'a  \nb\n' ),#trailing spaces
    ( 'x = 1 2\n', 'x = 12\n' ),#whitespace inside line
    ( 'a\tb\n', 'a    b\n' ),#tab vs spaces
    ( 'a\nb', 'a\nb\n' ),#missing newline at end of file
    ( 'a\nb\n', 'a\n\nb\n' ),#extra empty line
    ( 'a\r\nb\r\n', 'a\nb\n' ),#line endings
] )
def test_whitespace_only( ref, out ):
    d = reflogdiff.unified_diff_text( lines(ref), lines(out) )
    assert d.startswith( reflogdiff.whitespace_only_note + '\n' )
    assert '--- reference log\n+++ test output\n' in d

def test_real_differences():
    d = reflogdiff.unified_diff_text( lines('a\nvalue 1\n'), lines('a\nvalue 2\n') )
    assert reflogdiff.whitespace_only_note not in d
    assert '-value 1\n+value 2\n' in d

def test_no_newline_at_end():
    d = reflogdiff.unified_diff_text( lines('a\nb'), lines('a\nc') )
    assert d.endswith( '-b\n\\ No newline at end of file\n'
                       '+c\n\\ No newline at end of file\n' )

def test_compare_and_write_diff( tmp_path ):
    ref, out, diff = tmp_path / 'ref.log', tmp_path / 'out.log', tmp_path / 'diff.log'
    ref.write_bytes( b'abc\n\xff\xfe binary\n' )
    out.write_bytes( b'abc\n\xff\xfe binary\n' )
    assert reflogdiff.compare_and_write_diff( ref, out, diff )
    assert diff.read_bytes() == b''
    out.write_bytes( b'abc\n\xff\xfd binary\n' )
    assert not reflogdiff.compare_and_write_diff( ref, out, diff )
    assert b'-\xff\xfe binary\n+\xff\xfd binary\n' in diff.read_bytes()
