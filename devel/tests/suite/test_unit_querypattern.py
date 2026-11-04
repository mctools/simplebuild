import pytest

from _simple_build_system.querypattern import create_matcher

pytestmark = pytest.mark.unit

def _matches( pattern, text, force_ignorecase = False ):
    return bool( create_matcher( pattern, force_ignorecase ).search( text ) )

@pytest.mark.parametrize( 'pattern, text, expected', [
    #Plain text matches anywhere:
    ( 'collection', 'the HistCollection class', True ),
    ( 'xyz', 'the HistCollection class', False ),
    #Smart case:
    ( 'histcollection', 'HistCollection', True ),
    ( 'HistCollection', 'histcollection', False ),
    ( 'HistCollection', 'HistCollection', True ),
    #Wildcards:
    ( 'Foo*_Bar', 'Foo_Bar', True ),
    ( 'Foo*_Bar', 'Foo123_Bar', True ),
    ( 'Foo*_Bar', 'foo123_bar', False ),
    ( 'foo*_bar', 'Foo123_Bar', True ),
    ( 'f?o', 'fxo', True ),
    ( 'f?o', 'fo', False ),
    ( '*foo*', 'a foo b', True ),
    #A wildcard pattern also matches the text taken literally:
    ( 'int*', 'int* p', True ),
    ( 'const char*', 'const char* s', True ),
    #Other special characters match themselves:
    ( 'a.b', 'axb', False ),
    ( 'a.b', 'a.b', True ),
    ( 'f(x)', 'f(x)', True ),
    ( '[ab]', 'a', False ),
    ( '[ab]', '[ab]', True ),
    #Regular expressions:
    ( 'RE::^int\\s+\\w+', 'int foo', True ),
    ( 'RE::^int\\s+\\w+', 'x int foo', False ),
    ( 'RE::foo(bar|baz)', 'FOOBAZ', True ),
    ( 'RE::Foo(bar|baz)', 'foobaz', False ),
    #Escape sequences do not count as upper case letters:
    ( 'RE::\\Wfoo', ' FOO', True ),
    ( 'RE::(?i)Foo', 'foo', True ),
] )
def test_matching( pattern, text, expected ):
    assert _matches( pattern, text ) == expected

def test_force_ignorecase():
    assert _matches( 'HistCollection', 'histcollection', force_ignorecase = True )
    assert _matches( 'Foo*_Bar', 'FOO1_BAR', force_ignorecase = True )
    assert _matches( 'RE::Foo', 'foo', force_ignorecase = True )

def test_invalid_regex():
    with pytest.raises( SystemExit ) as e:
        create_matcher( 'RE::(' )
    assert 'Invalid regular expression in pattern "RE::("' in str( e.value )
