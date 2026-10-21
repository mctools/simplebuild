import pytest

from _simple_build_system.init_project import init_project
from _simple_build_system.singlecfg import SingleCfg

pytestmark = pytest.mark.unit

def do_init( tmp_path, monkeypatch, *args ):
    monkeypatch.chdir( tmp_path )
    init_project( args = list(args) )
    f = tmp_path / 'simplebuild.cfg'
    return f.read_text(), SingleCfg.create_from_toml_file( f )

def test_default( tmp_path, monkeypatch ):
    txt, cfg = do_init( tmp_path, monkeypatch )
    assert cfg.build_mode == 'release'
    assert list(cfg.depend_bundles) == ['core']
    assert cfg.build_extra_cflags == tuple()
    assert cfg.build_max_cachedirs == 5
    #The template documents the new options in comments:
    for e in ( "#   extra_cflags = '-ffp-contract=off'",
               "#   extra_ldflags = ['-Wl,--as-needed']",
               '#   max_cachedirs = 10' ):
        assert e in txt

@pytest.mark.parametrize( 'kw, mode', [ ( 'DEBUG', 'debug' ),
                                        ( 'RELDBG', 'reldbg' ),
                                        ( 'RELEASE', 'release' ) ] )
def test_modes( tmp_path, monkeypatch, kw, mode ):
    txt, cfg = do_init( tmp_path, monkeypatch, kw )
    assert cfg.build_mode == mode

def test_compact_and_options( tmp_path, monkeypatch ):
    txt, cfg = do_init( tmp_path, monkeypatch, 'core_val', 'COMPACT',
                        'CACHEDIR::/some/where', 'PKGFILTER::Foo*',
                        'PKGFILTER::!Bar' )
    assert '#' not in txt
    assert cfg.build_cachedir.name == 'where'
    assert list(cfg.build_pkg_filter) == [ 'Foo*', '!Bar' ]
    assert sorted(cfg.depend_bundles) == [ 'core', 'core_val' ]

def test_all_commented_examples_are_valid( tmp_path, monkeypatch ):
    #Uncomment each example line in the [build] section in turn, and check
    #that the result is a valid cfg file:
    txt, _ = do_init( tmp_path, monkeypatch )
    lines = txt.splitlines()
    ibuild = lines.index('[build]')
    examples = [ i for i, line in enumerate(lines)
                 if i > ibuild and line.startswith('  #   ') and ' = ' in line ]
    assert len(examples) >= 8
    for i in examples:
        if 'cachedir' in lines[i]:
            continue#refers to a non-existing directory
        modified = lines[:]
        modified[i] = lines[i].replace('  #   ','  ',1)
        f = tmp_path / 'simplebuild.cfg'
        f.write_text( '\n'.join(modified) + '\n' )
        SingleCfg.create_from_toml_file( f )

def test_refuse_existing_cfg( tmp_path, monkeypatch ):
    do_init( tmp_path, monkeypatch )
    with pytest.raises( SystemExit, match = 'conflicting file' ):
        do_init( tmp_path, monkeypatch )
