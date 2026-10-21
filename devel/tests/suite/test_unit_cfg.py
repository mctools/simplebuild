import warnings

import pytest

from _simple_build_system.singlecfg import SingleCfg

pytestmark = pytest.mark.unit

def load_cfg( tmp_path, content, ignore_build = False ):
    f = tmp_path / 'simplebuild.cfg'
    f.write_text( content )
    return SingleCfg.create_from_toml_file( f, ignore_build = ignore_build )

def load_build_section( tmp_path, *lines ):
    return load_cfg( tmp_path, '[bundle]\nname="test"\n[build]\n'
                     + '\n'.join(lines) + '\n' )

def test_defaults( tmp_path ):
    c = load_cfg( tmp_path, '[bundle]\nname="test"\n' )
    assert c.bundle_name == 'test'
    assert c.bundle_pkg_root == tmp_path.resolve()
    assert c.build_mode == 'release'
    assert c.build_cachedir == ( tmp_path / 'simplebuild_cache' ).resolve()
    assert c.build_pkg_filter == tuple()
    assert c.build_extra_cflags == tuple()
    assert c.build_extra_ldflags == tuple()
    assert c.build_max_cachedirs == 5
    assert list(c.depend_bundles) == ['core']

@pytest.mark.parametrize( 'mode', [ 'release', 'debug', 'reldbg' ] )
def test_modes( tmp_path, mode ):
    assert load_build_section( tmp_path, f'mode="{mode}"' ).build_mode == mode

def test_invalid_mode( tmp_path ):
    with pytest.raises( SystemExit, match = 'Invalid option "Debug"' ):
        load_build_section( tmp_path, 'mode="Debug"' )

@pytest.mark.parametrize( 'value', [
    "'-O2 -DFOO=1'",
    "['-O2','-DFOO=1']",
    "['-O2 -DFOO=1']",
    "[' -O2', '', '-DFOO=1 ']",
    "['-O2', \"'-DFOO=1'\"]",
] )
def test_extra_flags_string_or_list( tmp_path, value ):
    c = load_build_section( tmp_path, f'extra_cflags = {value}',
                            f'extra_ldflags = {value}' )
    assert c.build_extra_cflags == ('-O2','-DFOO=1')
    assert c.build_extra_ldflags == ('-O2','-DFOO=1')

@pytest.mark.parametrize( 'flag', [
    '-ffp-contract=off', '-std=c++20', '-march=x86-64-v3', '-Wl,--as-needed',
    '-DFOO=1', '-I/some/path', '-include', 'foo.h', '-Wl,-rpath,/a/b@c',
    '-fsanitize=address', '-DX=1%2', '-DA:B',
] )
def test_valid_flags( tmp_path, flag ):
    c = load_build_section( tmp_path, f"extra_cflags = ['{flag}']" )
    assert c.build_extra_cflags == (flag,)

@pytest.mark.parametrize( 'value', [
    "'-DFOO=\"a b\"'", "['$(FOO)']", "'-Wl,-rpath,$ORIGIN'", "'-DFOO=(1)'",
    "'-DA;B'", "'-DA#B'", "'-DA*B'", "'-DA|B'", "'-DA&B'", "'-DA<B'",
    "'-DA`B`'", "'-DA~B'", "'-DA!B'", "['-DA\\\\B']",
] )
def test_unsupported_flags( tmp_path, value ):
    with pytest.raises( SystemExit, match = 'Unsupported flag' ) as e:
        load_build_section( tmp_path, f'extra_cflags = {value}' )
    assert 'https://github.com/mctools/simplebuild/issues' in str(e.value)

@pytest.mark.parametrize( 'value, errmsg', [
    ( "17", 'expected string or list of strings' ),
    ( "['-O2', 17]", 'expected string or list of strings' ),
    ( "{ a = '-O2' }", 'expected string or list of strings' ),
    ( "'unbalanced \"quote'", 'No closing quotation' ),
] )
def test_invalid_flag_values( tmp_path, value, errmsg ):
    with pytest.raises( SystemExit, match = errmsg ):
        load_build_section( tmp_path, f'extra_ldflags = {value}' )

@pytest.mark.parametrize( 'value', [ 1, 5, 20 ] )
def test_max_cachedirs( tmp_path, value ):
    c = load_build_section( tmp_path, f'max_cachedirs = {value}' )
    assert c.build_max_cachedirs == value

@pytest.mark.parametrize( 'value', [ '0', '21', '-1', 'true', "'5'", '5.0' ] )
def test_invalid_max_cachedirs( tmp_path, value ):
    with pytest.raises( SystemExit, match = 'must be an integer from 1 to 20' ):
        load_build_section( tmp_path, f'max_cachedirs = {value}' )

def test_build_section_ignored_for_dependencies( tmp_path ):
    #Invalid build options are not even decoded for dependency bundles:
    c = load_cfg( tmp_path, '[bundle]\nname="test"\n[build]\nmax_cachedirs=0\n',
                  ignore_build = True )
    assert c.bundle_name == 'test'

def test_unknown_keys_give_warnings( tmp_path ):
    with warnings.catch_warnings( record = True ) as w:
        warnings.simplefilter('always')
        load_build_section( tmp_path, 'nosuchkey = 1' )
    assert any( 'Ignoring unknown simplebuild.cfg entry name "nosuchkey"'
                in str(e.message) for e in w )

def test_syntax_error( tmp_path ):
    with pytest.raises( SystemExit, match = 'Syntax error' ):
        load_cfg( tmp_path, '[bundle\n' )
