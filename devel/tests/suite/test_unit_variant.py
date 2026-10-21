import pytest

from _simple_build_system import variant

pytestmark = pytest.mark.unit

def _fast( args ):
    res = variant.fast_parse_leading_flags( args )
    if res is None:
        return None
    vf, rest = res
    return ( vf.mode, vf.ignore_extra_flags, rest )

@pytest.mark.parametrize( 'args, expected', [
    ( ['prog'], ( None, False, ['prog'] ) ),
    ( ['prog','-d','-x'], ( None, False, ['prog','-d','-x'] ) ),
    ( ['-d','prog'], ( 'debug', False, ['prog'] ) ),
    ( ['-r','prog'], ( 'release', False, ['prog'] ) ),
    ( ['-g','prog'], ( 'reldbg', False, ['prog'] ) ),
    ( ['-x','prog','a'], ( None, True, ['prog','a'] ) ),
    ( ['-xd','prog'], ( 'debug', True, ['prog'] ) ),
    ( ['-dx','prog'], ( 'debug', True, ['prog'] ) ),
    ( ['-x','-r','prog','-g'], ( 'release', True, ['prog','-g'] ) ),
    ( ['-dd','prog'], ( 'debug', False, ['prog'] ) ),
    ( ['-xx','prog'], ( None, True, ['prog'] ) ),
] )
def test_fast_parse_valid( args, expected ):
    assert _fast( args ) == expected

@pytest.mark.parametrize( 'args', [
    [], ['-x'], ['-d','-x'],#no program
    ['-dr','prog'], ['-d','-g','prog'], ['-xrg','prog'],#conflicting modes
    ['-h','prog'], ['--help'], ['-q','prog'], ['-','prog'], ['--x','prog'],
] )
def test_fast_parse_falls_back_to_argparse( args ):
    assert _fast( args ) is None

def test_parse_launcher_args_valid():
    vf, rest = variant.parse_launcher_args( 'sbrun', ['-x','-g','prog','-x'],
                                            'descr' )
    assert ( vf.mode, vf.ignore_extra_flags, rest ) == ( 'reldbg', True,
                                                         ['prog','-x'] )

@pytest.mark.parametrize( 'args, errmsg', [
    ( ['-dr','prog'], 'not allowed with argument' ),
    ( ['-x'], 'missing program to run' ),
    ( ['-q','prog'], 'unrecognized arguments' ),
    ( ['--nosuchflag','prog'], 'unrecognized arguments' ),
] )
def test_parse_launcher_args_errors( args, errmsg, capsys ):
    with pytest.raises( SystemExit ) as e:
        variant.parse_launcher_args( 'sbrun', args, 'descr' )
    assert e.value.code == 2
    assert errmsg in capsys.readouterr().err

def test_parse_launcher_args_help( capsys ):
    with pytest.raises( SystemExit ) as e:
        variant.parse_launcher_args( 'sbenv', ['-h','prog'], 'Some descr' )
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert 'usage: sbenv [-h] [-d|-r|-g] [-x] <program> [args]' in out
    assert 'Some descr' in out

def test_mode_flag():
    assert variant.VariantFlags().mode_flag() is None
    assert variant.VariantFlags('debug').mode_flag() == '-d'
    assert variant.VariantFlags('release').mode_flag() == '-r'
    assert variant.VariantFlags('reldbg').mode_flag() == '-g'

def test_cachedir_suffix():
    #Names without extra flags must stay as in earlier simplebuild versions:
    assert variant.cachedir_suffix( 'release', (), () ) == ''
    assert variant.cachedir_suffix( 'debug', (), () ) == '_debug'
    assert variant.cachedir_suffix( 'reldbg', (), () ) == '_reldbg'
    #The hash of the extra flags should be stable between versions (to avoid
    #unnecessary rebuilds after upgrades):
    assert variant.cachedir_suffix( 'release', ('-O2',), () ) == '_xff636e205d8'
    assert variant.cachedir_suffix( 'debug', ('-ffp-contract=off',),
                                    ('-Wl,--as-needed',) ) == '_debug_xf4c2eae71c3'
    #cflags and ldflags are not interchangeable:
    assert variant.cachedir_suffix( 'reldbg', (), ('-O2',) ) == '_reldbg_xf02e5f000c8'

def test_extra_flags_description():
    d = variant.extra_flags_description
    assert d( (), () ) == ''
    assert d( ('-O2','-g'), () ) == 'extra_cflags: -O2 -g'
    assert d( (), ('-lm',) ) == 'extra_ldflags: -lm'
    assert d( ('-O2',), ('-lm',) ) == 'extra_cflags: -O2  extra_ldflags: -lm'
