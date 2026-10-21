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
