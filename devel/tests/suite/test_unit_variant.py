import pytest

from _simple_build_system import variant

pytestmark = pytest.mark.unit

def _fast( args ):
    res = variant.fast_parse_leading_flags( args )
    if res is None:
        return None
    vf, rest = res
    return ( vf.mode, vf.ignore_extra_flags, vf.flagset, rest )

@pytest.mark.parametrize( 'args, expected', [
    ( ['prog'], ( None, False, None, ['prog'] ) ),
    ( ['prog','-d','-x'], ( None, False, None, ['prog','-d','-x'] ) ),
    ( ['-d','prog'], ( 'debug', False, None, ['prog'] ) ),
    ( ['-r','prog'], ( 'release', False, None, ['prog'] ) ),
    ( ['-g','prog'], ( 'reldbg', False, None, ['prog'] ) ),
    ( ['-x','prog','a'], ( None, True, None, ['prog','a'] ) ),
    ( ['-xd','prog'], ( 'debug', True, None, ['prog'] ) ),
    ( ['-dx','prog'], ( 'debug', True, None, ['prog'] ) ),
    ( ['-x','-r','prog','-g'], ( 'release', True, None, ['prog','-g'] ) ),
    ( ['-dd','prog'], ( 'debug', False, None, ['prog'] ) ),
    ( ['-xx','prog'], ( None, True, None, ['prog'] ) ),
    ( ['-X','fma','prog'], ( None, False, 'fma', ['prog'] ) ),
    ( ['-Xfma','prog','-X','b'], ( None, False, 'fma', ['prog','-X','b'] ) ),
    ( ['-dXfma','prog'], ( 'debug', False, 'fma', ['prog'] ) ),
    ( ['-gX','fma_2-b','prog'], ( 'reldbg', False, 'fma_2-b', ['prog'] ) ),
    ( ['-X','fma','-r','prog'], ( 'release', False, 'fma', ['prog'] ) ),
] )
def test_fast_parse_valid( args, expected ):
    assert _fast( args ) == expected

@pytest.mark.parametrize( 'args', [
    [], ['-x'], ['-d','-x'],#no program
    ['-dr','prog'], ['-d','-g','prog'], ['-xrg','prog'],#conflicting modes
    ['-h','prog'], ['--help'], ['-q','prog'], ['-','prog'], ['--x','prog'],
    ['-X'], ['-X','fma'], ['-Xfma'],#no program (or name)
    ['-x','-X','fma','prog'], ['-Xfma','-x','prog'],#-x and -X conflict
    ['-X','a','-X','b','prog'],#several flag sets
    ['-X','-d','prog'], ['-X','a.b','prog'], ['-X','','prog'],#invalid names
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
    ( ['-x','-X','fma','prog'], 'not allowed with argument' ),
    ( ['-X'], 'expected one argument' ),
    #(the name of the flag set is not taken as the program:)
    ( ['-X','fma','-dr','prog'], 'not allowed with argument' ),
    ( ['-X','fma'], 'missing program to run' ),
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
    assert 'usage: sbenv [-h] [-d|-r|-g] [-x|-X NAME] <program> [args]' in out
    assert 'Some descr' in out

def test_mode_flag():
    assert variant.VariantFlags().mode_flag() is None
    assert variant.VariantFlags('debug').mode_flag() == '-d'
    assert variant.VariantFlags('release').mode_flag() == '-r'
    assert variant.VariantFlags('reldbg').mode_flag() == '-g'

def test_as_args():
    V = variant.VariantFlags
    assert V().as_args() == []
    assert V('debug',True).as_args() == ['-d','-x']
    assert V('reldbg',flagset='fma').as_args() == ['-g','-X','fma']

@pytest.mark.parametrize( 'name, valid', [
    ( 'fma', True ), ( 'no_contract-2', True ), ( '_a', True ), ( '9', True ),
    ( '', False ), ( '-a', False ), ( 'a b', False ), ( ' a', False ),
    ( 'a.b', False ), ( 'a/b', False ), ( 'æ', False ),
] )
def test_is_valid_flagset_name( name, valid ):
    assert variant.is_valid_flagset_name( name ) == valid

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
