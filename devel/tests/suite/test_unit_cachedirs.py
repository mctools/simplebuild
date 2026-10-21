import os

import pytest

from _simple_build_system import cachedirs

pytestmark = pytest.mark.unit

def make_cachedir( cachedir, suffix, last_used = None, *, fingerprints = True,
                   locked = False, with_install = True ):
    bld = cachedir / f'bld{suffix}'
    inst = cachedir / f'install{suffix}'
    bld.mkdir( parents = True )
    if with_install:
        inst.mkdir()
    if fingerprints:
        ( bld / '.sbbuilddir' ).touch()
        if with_install:
            ( inst / '.sbinstalldir' ).touch()
    if locked:
        ( bld / '.lock' ).write_text('12345')
    if last_used is not None:
        f = bld / cachedirs.last_used_filename
        f.touch()
        os.utime( f, ( last_used, last_used ) )
    return bld

def names( cachedir ):
    return sorted( f.name for f in cachedir.iterdir() )

def test_find_cachedirs( tmp_path ):
    for s in ( '', '_debug', '_reldbg', '_xf0123456789', '_debug_xfabcdef0123' ):
        make_cachedir( tmp_path, s )
    #Things which must be ignored:
    for n in ( 'bld_foo', 'install_xf123', 'bldx', 'other', 'bld_release',
               'bld_reldbg_xfABCDEF0123' ):
        ( tmp_path / n ).mkdir()
    found = sorted( cd.suffix for cd in cachedirs.find_cachedirs( tmp_path ) )
    assert found == sorted( [ '', '_debug', '_reldbg', '_xf0123456789',
                              '_debug_xfabcdef0123' ] )
    assert cachedirs.find_cachedirs( tmp_path / 'nonexisting' ) == []

def test_touch_last_used( tmp_path ):
    bld = tmp_path / 'bld'
    cachedirs.touch_last_used( bld, create_missing = False )
    assert not bld.exists()
    bld.mkdir()
    cachedirs.touch_last_used( bld, create_missing = False )
    assert ( bld / cachedirs.last_used_filename ).exists()

def test_remove_least_recently_used( tmp_path ):
    current = make_cachedir( tmp_path, '_debug', 100 )#oldest, but in use
    make_cachedir( tmp_path, '', 200 )
    make_cachedir( tmp_path, '_reldbg', 300 )
    make_cachedir( tmp_path, '_xf0123456789', 400 )
    make_cachedir( tmp_path, '_debug_xf0123456789', 500 )
    removed = cachedirs.remove_least_recently_used( tmp_path, current, 3 )
    assert [ cd.suffix for cd in removed ] == [ '', '_reldbg' ]
    assert names( tmp_path ) == sorted( [ 'bld_debug', 'install_debug',
                                          'bld_xf0123456789',
                                          'install_xf0123456789',
                                          'bld_debug_xf0123456789',
                                          'install_debug_xf0123456789' ] )
    #Nothing more to do:
    assert cachedirs.remove_least_recently_used( tmp_path, current, 3 ) == []
    #Only the current one left with max=1:
    removed = cachedirs.remove_least_recently_used( tmp_path, current, 1 )
    assert len(removed) == 2
    assert names( tmp_path ) == [ 'bld_debug', 'install_debug' ]

def test_remove_lru_skips_locked_and_unknown( tmp_path ):
    current = make_cachedir( tmp_path, '', 500 )
    make_cachedir( tmp_path, '_debug', 100, locked = True )
    make_cachedir( tmp_path, '_reldbg', 200, fingerprints = False )
    make_cachedir( tmp_path, '_xf0123456789', 300 )
    make_cachedir( tmp_path, '_debug_xf0123456789', 400 )
    #The unknown one (no fingerprints) does not count, the locked one counts
    #but can not be removed:
    removed = cachedirs.remove_least_recently_used( tmp_path, current, 2 )
    assert [ cd.suffix for cd in removed ] == [ '_xf0123456789',
                                                '_debug_xf0123456789' ]
    assert names( tmp_path ) == sorted( [ 'bld', 'install',
                                          'bld_debug', 'install_debug',
                                          'bld_reldbg', 'install_reldbg' ] )

def test_last_used_fallbacks( tmp_path ):
    #Cache dirs from older simplebuild versions have no last_used file (and
    #those are considered older than any with such files):
    current = make_cachedir( tmp_path, '', 500 )
    make_cachedir( tmp_path, '_debug', 100 )
    old = make_cachedir( tmp_path, '_reldbg' )
    os.utime( old, ( 50, 50 ) )
    removed = cachedirs.remove_least_recently_used( tmp_path, current, 2 )
    assert [ cd.suffix for cd in removed ] == [ '_reldbg' ]

def test_partial_cachedirs( tmp_path ):
    #A bld dir without install dir (e.g. created by sb -c or a query) is
    #still a valid cache dir:
    current = make_cachedir( tmp_path, '', 500 )
    make_cachedir( tmp_path, '_debug', 100, with_install = False )
    removed = cachedirs.remove_least_recently_used( tmp_path, current, 1 )
    assert [ cd.suffix for cd in removed ] == [ '_debug' ]
    assert names( tmp_path ) == [ 'bld', 'install' ]

def test_never_remove_symlinks_or_files( tmp_path ):
    current = make_cachedir( tmp_path, '', 500 )
    target = tmp_path / 'target'
    target.mkdir()
    ( target / '.sbbuilddir' ).touch()
    ( tmp_path / 'bld_debug' ).symlink_to( target )
    ( tmp_path / 'install_reldbg' ).write_text('not a dir')
    assert cachedirs.remove_least_recently_used( tmp_path, current, 1 ) == []
    assert ( target / '.sbbuilddir' ).exists()
    assert ( tmp_path / 'install_reldbg' ).exists()

def test_remove_all( tmp_path ):
    current = make_cachedir( tmp_path, '', locked = True )#our own lock
    make_cachedir( tmp_path, '_debug' )
    make_cachedir( tmp_path, '_reldbg', locked = True )
    make_cachedir( tmp_path, '_xf0123456789', fingerprints = False )
    removed, skipped = cachedirs.remove_all( tmp_path, current )
    assert sorted( cd.suffix for cd in removed ) == [ '', '_debug' ]
    assert sorted( cd.suffix for cd in skipped ) == [ '_reldbg', '_xf0123456789' ]
    assert names( tmp_path ) == sorted( [ 'bld_reldbg', 'install_reldbg',
                                          'bld_xf0123456789',
                                          'install_xf0123456789' ] )

def test_write_extra_flags_file( tmp_path ):
    cachedirs.write_extra_flags_file( tmp_path, ('-O2','-g'), () )
    content = ( tmp_path / cachedirs.extra_flags_filename ).read_text()
    assert 'extra_cflags: -O2 -g\n' in content
    assert 'extra_ldflags: \n' in content
