import pytest

from _simple_build_system.pkgfilter import PkgFilter

pytestmark = pytest.mark.unit

#Packages as (name, reldir) tuples:
_pkgs = [ ( 'MyPkg', 'some/where/MyPkg' ),
          ( 'MyOtherPkg', 'MyOtherPkg' ),
          ( 'MyBrokenPkg', 'MyBrokenPkg' ),
          ( 'MyUtils', 'utils/MyUtils' ),
          ( 'MyUtilsTests', 'utils/MyUtilsTests' ),
          ( 'MyUtils_tests', 'utils/MyUtils_tests' ),
          ( 'My_utils', 'My_utils' ),
          ( 'Core', 'Core' ) ]

def passing( filters ):
    f = PkgFilter( filters )
    return sorted( n for n, d in _pkgs if f.passes( n, d ) )

def test_fully_open():
    assert PkgFilter( [] ).fully_open()
    assert PkgFilter( [ '', '!', ' , ' ] ).fully_open()
    assert not PkgFilter( [ 'MyPkg' ] ).fully_open()
    assert passing( [] ) == sorted( n for n, d in _pkgs )

#Examples from the documentation (simplebuilddotcfg.rst):
@pytest.mark.parametrize( 'filters, expected', [
    ( ['MyPkg','MyOtherPkg'], ['MyOtherPkg','MyPkg'] ),
    ( ['!MyPkg'], sorted( n for n, d in _pkgs if n != 'MyPkg' ) ),
    ( ['My*'], sorted( n for n, d in _pkgs if n.startswith('My') ) ),
    ( ['some/where/*'], ['MyPkg'] ),
    ( ['RE::.*Util.*','!RE::(?i).*test.*'], ['MyUtils'] ),
    ( ['My*','!MyBrokenPkg'],
      sorted( n for n, d in _pkgs if n.startswith('My') and n != 'MyBrokenPkg' ) ),
] )
def test_documented_examples( filters, expected ):
    assert passing( filters ) == expected

def test_comma_separation_is_equivalent():
    assert ( PkgFilter( [ 'My*','!MyBrokenPkg' ] ).as_string()
             == PkgFilter( [ 'My*,!MyBrokenPkg' ] ).as_string() )
    assert passing( [ 'My*','!MyBrokenPkg' ] ) == passing( [ 'My*,!MyBrokenPkg' ] )

def test_absolute_paths_not_supported():
    with pytest.raises( SystemExit, match = 'Absolute paths not supported' ):
        PkgFilter( [ '/some/where/*' ] )

def test_invalid_regex():
    with pytest.raises( SystemExit, match = 'Invalid syntax in pkg filter' ):
        PkgFilter( [ 'RE::(unbalanced' ] )
