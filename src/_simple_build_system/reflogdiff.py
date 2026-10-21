# Comparison of the output of tests with their reference logs.
#
# The comparison is exact (byte by byte). When the output differs from the
# reference log only in whitespace (e.g. trailing spaces removed by an editor),
# this is pointed out explicitly, since such differences are otherwise hard to
# spot.

whitespace_only_note = ( 'NOTE: The output differs from the reference log'
                         ' only in whitespace (e.g. trailing spaces).' )

def read_lines( path ):
    """Read file as a list of lines (including line endings). Bytes which are
    not valid UTF-8 are preserved (as surrogate escapes)."""
    import pathlib
    data = pathlib.Path(path).read_bytes()
    return data.decode( 'utf-8', errors = 'surrogateescape' ).splitlines( True )

def differs_only_in_whitespace( lines_a, lines_b ):
    """Whether the two lists of lines are equal when ignoring all whitespace
    (including line breaks and empty lines)."""
    import re
    def strip( lines ):
        return re.sub( r'\s+', '', ''.join(lines) )
    return strip(lines_a) == strip(lines_b)

def unified_diff_text( ref_lines, out_lines ):
    """Differences in the unified diff format, preceded by a note if the
    differences are only in whitespace. Returns an empty string if there are no
    differences."""
    if ref_lines == out_lines:
        return ''
    import difflib
    res = []
    if differs_only_in_whitespace( ref_lines, out_lines ):
        res.append( whitespace_only_note + '\n' )
    for line in difflib.unified_diff( ref_lines, out_lines,
                                      'reference log', 'test output' ):
        if not line.endswith('\n'):
            line += '\n\\ No newline at end of file\n'
        res.append( line )
    return ''.join(res)

def compare_and_write_diff( reflog, output, difffile ):
    """Compare the output of a test with its reference log, and write the
    differences (if any) to difffile (empty if there are no differences).
    Returns True if they are identical."""
    from .utils import write_atomic
    txt = unified_diff_text( read_lines(reflog), read_lines(output) )
    write_atomic( difffile, txt.encode( 'utf-8', errors = 'surrogateescape' ) )
    return not txt
