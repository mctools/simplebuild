import os
import pickle

import pytest

from _simple_build_system import utils

pytestmark = pytest.mark.unit

def test_write_atomic( tmp_path ):
    f = tmp_path / 'file.txt'
    utils.write_atomic( f, 'hello' )
    assert f.read_text() == 'hello'
    utils.write_atomic( f, b'\x00bytes' )
    assert f.read_bytes() == b'\x00bytes'
    utils.write_atomic( f, 'x', mode = 0o755 )
    assert os.stat( f ).st_mode & 0o777 == 0o755
    assert sorted( p.name for p in tmp_path.iterdir() ) == [ 'file.txt' ]

def test_write_atomic_failure_leaves_original( tmp_path ):
    f = tmp_path / 'file.txt'
    f.write_text( 'original' )
    class Bad:
        pass
    with pytest.raises( TypeError ):
        utils.write_atomic( f, Bad() )
    assert f.read_text() == 'original'
    assert sorted( p.name for p in tmp_path.iterdir() ) == [ 'file.txt' ]

def test_pkl_load_or_none( tmp_path ):
    f = tmp_path / 'data.pkl'
    assert utils.pkl_load_or_none( f ) is None
    utils.pkl_dump( { 'a' : 1 }, f )
    assert utils.pkl_load_or_none( f ) == { 'a' : 1 }
    #Truncated file:
    data = pickle.dumps( list(range(1000)) )
    f.write_bytes( data[:len(data)//2] )
    assert utils.pkl_load_or_none( f, warn_if_broken = False ) is None
    assert not f.exists()#broken files are removed
    #Garbage:
    f.write_bytes( b'not a pickle' )
    assert utils.pkl_load_or_none( f, warn_if_broken = False ) is None
    f.write_bytes( b'' )
    assert utils.pkl_load_or_none( f, warn_if_broken = False ) is None

def test_update_pkl_if_changed( tmp_path ):
    f = tmp_path / 'data.pkl'
    old = tmp_path / 'data.pkl.old'
    assert utils.update_pkl_if_changed( { 1, 2 }, f ) is None
    assert utils.pkl_load( f ) == { 1, 2 } and not old.exists()
    mtime = f.stat().st_mtime_ns
    #Unchanged content: file untouched:
    assert utils.update_pkl_if_changed( { 1, 2 }, f ) == { 1, 2 }
    assert f.stat().st_mtime_ns == mtime and not old.exists()
    #Changed content: previous content moved to .old:
    assert utils.update_pkl_if_changed( { 3 }, f ) == { 1, 2 }
    assert utils.pkl_load( f ) == { 3 } and utils.pkl_load( old ) == { 1, 2 }
    #Falsy content works:
    assert utils.update_pkl_if_changed( False, f ) == { 3 }
    assert utils.update_pkl_if_changed( False, f ) is False
    #Broken file is simply replaced:
    f.write_bytes( b'broken' )
    assert utils.update_pkl_if_changed( { 4 }, f ) is None
    assert utils.pkl_load( f ) == { 4 }

def _links( d ):
    return { p.name : os.readlink( p ) for p in d.iterdir() if p.is_symlink() }

def test_update_symlinks( tmp_path ):
    src = tmp_path / 'src'
    src.mkdir()
    for n in ( 'a', 'b', 'c' ):
        ( src / n ).write_text( n )
    dest = tmp_path / 'dest'
    def entry( name, srcname ):
        return ( str(dest), name, str( src / srcname ) )
    utils.update_symlinks( set(), { entry('la','a'), entry('lb','b') }, False )
    assert _links( dest ) == { 'la' : str(src/'a'), 'lb' : str(src/'b') }
    #Correct links are left untouched:
    ino = os.lstat( dest / 'la' ).st_ino
    #Dangling and wrong links are replaced, and regular files in the way too:
    ( dest / 'lb' ).unlink()
    ( dest / 'lb' ).symlink_to( src / 'nonexisting' )
    ( dest / 'lc' ).write_text( 'in the way' )
    old = { entry('la','a'), entry('lb','b') }
    new = { entry('la','a'), entry('lb','c'), entry('lc','c') }
    utils.update_symlinks( old, new, False )
    assert os.lstat( dest / 'la' ).st_ino == ino
    assert _links( dest ) == { 'la' : str(src/'a'), 'lb' : str(src/'c'),
                               'lc' : str(src/'c') }
    #Obsolete links are removed (also if already gone), and empty dirs too:
    ( dest / 'lc' ).unlink()
    utils.update_symlinks( new, set(), False )
    assert not dest.exists()

def test_update_symlinks_dir_in_the_way( tmp_path ):
    dest = tmp_path / 'dest'
    ( dest / 'la' ).mkdir( parents = True )
    with pytest.raises( SystemExit, match = 'Directory found where a symlink' ):
        utils.update_symlinks( set(), { ( str(dest), 'la', '/some/where' ) },
                               False )

def test_install_symlinks_from_pickle( tmp_path ):
    #The state of what was actually installed is remembered, so links are
    #correctly removed even if the .old file does not reflect what was
    #installed (e.g. after a build failed before the installation step):
    src = tmp_path / 'src'
    src.mkdir()
    for n in ( 'a', 'b' ):
        ( src / n ).write_text( n )
    dest = tmp_path / 'dest'
    pkl = tmp_path / 'links.pkl'
    def load( f ):
        d = utils.pkl_load_or_none( f )
        return d if isinstance( d, set ) else None
    ea = ( str(dest), 'la', str(src/'a') )
    eb = ( str(dest), 'lb', str(src/'b') )
    utils.update_pkl_if_changed( { ea, eb }, pkl )
    utils.install_symlinks_from_pickle( pkl, load, False )
    assert set( _links( dest ) ) == { 'la', 'lb' }
    #Configure twice without installing in between (so the .old file no longer
    #contains eb):
    utils.update_pkl_if_changed( { ea }, pkl )
    utils.update_pkl_if_changed( set(), pkl )
    assert load( tmp_path / 'links.pkl.old' ) == { ea }
    utils.install_symlinks_from_pickle( pkl, load, False )
    assert not dest.exists()
    #Broken needed file gives a clear error:
    pkl.write_bytes( b'broken' )
    with pytest.raises( SystemExit, match = 'Could not load' ):
        utils.install_symlinks_from_pickle( pkl, load, False )

@pytest.fixture
def cache_and_userfiles( tmp_path ):
    #A cache dir (with fingerprint file), and user files outside of it which
    #are referred to by symlinks inside it (like the symlinks to package
    #directories created by simplebuild):
    root = tmp_path / 'cache'
    user = tmp_path / 'user'
    ( user / 'subdir' ).mkdir( parents = True )
    ( user / 'file.txt' ).write_text( 'user file' )
    ( user / 'subdir' / 'file2.txt' ).write_text( 'user file 2' )
    root.mkdir()
    ( root / '.sbbuilddir' ).touch()
    ( root / 'a' / 'b' ).mkdir( parents = True )
    ( root / 'a' / 'b' / 'f.txt' ).write_text( 'cache file' )
    ( root / 'a' / 'link_to_userdir' ).symlink_to( user )
    ( root / 'a' / 'b' / 'link_to_userfile' ).symlink_to( user / 'file.txt' )
    ( root / 'link_to_userdir' ).symlink_to( user, target_is_directory = True )
    ( root / 'reldirlink' ).symlink_to( '../user' )
    return root, user

def _userfiles_intact( user ):
    return ( ( user / 'file.txt' ).read_text() == 'user file'
             and ( user / 'subdir' / 'file2.txt' ).read_text() == 'user file 2' )

def test_remove_within( cache_and_userfiles ):
    root, user = cache_and_userfiles
    #Symlinks to directories are removed, not followed:
    for lnk in ( root / 'link_to_userdir', root / 'reldirlink' ):
        utils.remove_within( lnk, root )
        assert not os.path.lexists( lnk )
        assert _userfiles_intact( user )
    #Directory trees with symlinks inside are removed without following
    #symlinks:
    utils.remove_within( root / 'a', root )
    assert not ( root / 'a' ).exists()
    assert _userfiles_intact( user )
    assert ( root / '.sbbuilddir' ).exists()
    #Removing non-existing files is not an error:
    utils.remove_within( root / 'a', root )
    utils.remove_within( root / 'nonexisting' / 'file', root )

def test_remove_within_files( cache_and_userfiles ):
    root, user = cache_and_userfiles
    utils.remove_within( root / 'a' / 'b' / 'link_to_userfile', root )
    utils.remove_within( root / 'a' / 'b' / 'f.txt', root )
    assert sorted( os.listdir( root / 'a' / 'b' ) ) == []
    assert _userfiles_intact( user )

def test_remove_within_refuses_unsafe_paths( cache_and_userfiles, tmp_path ):
    root, user = cache_and_userfiles
    unsafe = [ root,#the root itself
               tmp_path,
               user,
               user / 'file.txt',
               root / '..' / 'user',#escapes lexically
               root / 'a' / '..' / '..' / 'user' / 'file.txt',
               #inside root lexically, but really outside via symlinks:
               root / 'link_to_userdir' / 'file.txt',
               root / 'link_to_userdir' / 'subdir',
               root / 'a' / 'link_to_userdir' / 'subdir' / 'file2.txt' ]
    for p in unsafe:
        with pytest.raises( RuntimeError ):
            utils.remove_within( p, root )
        assert _userfiles_intact( user )
    assert ( root / 'a' / 'b' / 'f.txt' ).exists()
    #Also with paths as strings, and relative paths:
    with pytest.raises( RuntimeError ):
        utils.remove_within( str( root / 'link_to_userdir' / 'subdir' ),
                             str( root ) )
    cwd = os.getcwd()
    try:
        os.chdir( root )
        with pytest.raises( RuntimeError ):
            utils.remove_within( '../user', '.' )
        with pytest.raises( RuntimeError ):
            utils.remove_within( 'link_to_userdir/file.txt', '.' )
    finally:
        os.chdir( cwd )
    assert _userfiles_intact( user )

def test_remove_within_requires_fingerprint( tmp_path ):
    d = tmp_path / 'notacache'
    ( d / 'sub' ).mkdir( parents = True )
    with pytest.raises( RuntimeError ):
        utils.remove_within( d / 'sub', d )
    assert ( d / 'sub' ).is_dir()

def test_remove_glob_within( cache_and_userfiles ):
    root, user = cache_and_userfiles
    utils.remove_glob_within( root, 'link_*', root )
    assert not os.path.lexists( root / 'link_to_userdir' )
    assert os.path.lexists( root / 'reldirlink' )
    #Globbing in a symlinked dir is refused:
    utils.remove_glob_within( root / 'reldirlink', '*', root )
    assert _userfiles_intact( user )

def test_remove_cache_dir( cache_and_userfiles, tmp_path ):
    root, user = cache_and_userfiles
    utils.remove_cache_dir( root )
    assert not os.path.lexists( root )
    assert _userfiles_intact( user )
    #Directories without fingerprint file, and symlinks to directories with
    #fingerprint files, are left untouched:
    utils.remove_cache_dir( user )
    assert _userfiles_intact( user )
    ( user / '.sbinstalldir' ).touch()
    lnk = tmp_path / 'link_to_cache'
    lnk.symlink_to( user )
    utils.remove_cache_dir( lnk )
    assert lnk.is_symlink() and _userfiles_intact( user )
    #Nonexisting dirs are not an error:
    utils.remove_cache_dir( tmp_path / 'nonexisting' )
