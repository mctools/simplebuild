import pytest

from _simple_build_system.parse_args import parse_args

pytestmark = pytest.mark.unit

def sbargs( *args ):
    return parse_args( argv = [ 'sb' ] + list(args) )

@pytest.mark.parametrize( 'args, mode, ignore_extra, runtests', [
    ( [], None, False, False ),
    ( ['-d'], 'debug', False, False ),
    ( ['-r'], 'release', False, False ),
    ( ['-g'], 'reldbg', False, False ),
    ( ['-x'], None, True, False ),
    ( ['-tdx'], 'debug', True, True ),
    ( ['-x','-r'], 'release', True, False ),
    ( ['-gx','-t'], 'reldbg', True, True ),
] )
def test_variant_flags( args, mode, ignore_extra, runtests ):
    o = sbargs( *args )
    assert ( o.variant_mode, o.variant_ignore_extra_flags, o.runtests ) == (
        mode, ignore_extra, runtests )

@pytest.mark.parametrize( 'args', [ ['-dr'], ['-d','-g'], ['-xrg'], ['-r','-d'] ] )
def test_conflicting_modes( args, capsys ):
    with pytest.raises( SystemExit ) as e:
        sbargs( *args )
    assert e.value.code == 2
    assert 'not allowed with argument' in capsys.readouterr().err

def test_no_long_variant_options( capsys ):
    for a in ( '--debug', '--release', '--reldbg', '--no-extra-flags' ):
        with pytest.raises( SystemExit ):
            sbargs( a )

def test_help_has_variant_group( capsys ):
    with pytest.raises( SystemExit ) as e:
        sbargs( '-h' )
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert 'Selecting the build variant:' in out
    for flag in ( '-d', '-r', '-g', '-x' ):
        assert f'\n  {flag}  ' in out

@pytest.mark.parametrize( 'args', [ ['-c','-t'], ['--grep','foo','-c'],
                                    ['--version','-s'] ] )
def test_exclusive_options( args ):
    with pytest.raises( SystemExit ):
        sbargs( *args )

def test_init_args():
    o = sbargs( '--init', 'core_val', 'DEBUG', 'COMPACT', 'CACHEDIR::/a/b',
                'PKGFILTER::Foo*' )
    assert o.init == [ 'core_val', 'DEBUG', 'COMPACT', 'CACHEDIR::/a/b',
                       'PKGFILTER::Foo*' ]
    with pytest.raises( SystemExit ):
        sbargs( '--init', 'DEBUG', 'RELEASE' )
    with pytest.raises( SystemExit ):
        sbargs( '--init', 'Invalid-Name' )
