# Patterns of the --grep and --find query options (and their variants):
#
#   * By default, "*" matches any sequence of characters and "?" any single
#     character, and all other characters match themselves. The pattern can
#     match anywhere (e.g. in a line for --grep).
#   * With the prefix "RE::", the rest of the pattern is a (Python) regular
#     expression.
#   * Smart case: patterns without upper case letters ignore case, other
#     patterns are case sensitive, unless ignore case is requested explicitly
#     (by --grepi, --grepci, and --findi). For regular expressions, escape
#     sequences like \W or \S do not count as upper case letters.

import re

def create_matcher( pattern, force_ignorecase = False ):
    """Returns compiled regular expression for the pattern, to be used with
    .search(..) or .finditer(..)."""
    if pattern.startswith('RE::'):
        regex = pattern[4:]
        casecheck = re.sub( r'\\.', '', regex )
    else:
        #Leading and trailing "*" have no effect on where the pattern matches
        #(but would make highlighted matches extend to the start or end of the
        #lines):
        casecheck = pattern.strip('*')
        regex = ''.join( ( '.*' if c == '*' else ( '.' if c == '?' else re.escape(c) ) )
                         for c in casecheck )
    ignorecase = force_ignorecase or not any( c.isupper() for c in casecheck )
    try:
        return re.compile( regex, re.IGNORECASE if ignorecase else 0 )
    except re.error as e:
        from . import error
        error.error(f'Invalid regular expression in pattern "{pattern}": {e}')
