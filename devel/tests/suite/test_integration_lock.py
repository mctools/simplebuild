# The lock preventing concurrent sb invocations on the same cache directory,
# and query options (issues #72 and #30 on GitHub).

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

#Script reporting whether the lock of the cache dir is currently held. With
#the "--require" argument, it fails if not (making it suitable as a test):
_checklock_script = '''#!/usr/bin/env python3
import os
import pathlib
import sys
inst = pathlib.Path(os.environ['SBLD_INSTALL_PREFIX'])
lockfile = inst.parent / inst.name.replace('install','bld',1) / '.lock'
locked = lockfile.exists()
print('LOCKED' if locked else 'UNLOCKED')
if '--require' in sys.argv[1:] and not locked:
    raise SystemExit(1)
'''

@pytest.fixture
def lockproj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/checklock' : _checklock_script,
        'MyPkg/scripts/testlockheld' : '#!/usr/bin/env bash\nexec sb_mypkg_checklock --require\n',
    } )
    for f in ( 'checklock', 'testlockheld' ):
        ( d / 'MyPkg' / 'scripts' / f ).chmod( 0o755 )
    return d

def test_lock_held_during_build_and_tests( lockproj ):
    d = lockproj
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    run( 'sb -t', d )
    assert not lockfile.exists()
    #The lock must also be held after the cache dir is wiped by --insist:
    run( 'sb -t --insist', d )
    assert not lockfile.exists()
    #Also in other variants:
    run( 'sb -d -t --insist', d )
    assert not ( d / 'simplebuild_cache' / 'bld_debug' / '.lock' ).exists()

def test_sbrun_releases_lock( lockproj ):
    #Issue #72: sbrun must release the lock before launching the command, so
    #other sb invocations can proceed while the command runs:
    d = lockproj
    res = run( 'sbrun sb_mypkg_checklock', d )
    assert res.stdout.strip() == 'UNLOCKED'
    res = run( 'sbrun -d sb_mypkg_checklock', d )
    assert res.stdout.strip() == 'UNLOCKED'
    res = run( [ 'sbrun', 'bash', '-c', 'sb -q && echo NESTED_SB_OK' ], d )
    assert 'NESTED_SB_OK' in res.stdout

def test_competing_invocation_detected( lockproj ):
    d = lockproj
    run( 'sb', d )
    lockfile = d / 'simplebuild_cache' / 'bld' / '.lock'
    lockfile.write_text( '999999999' )
    res = run( 'sb', d, expect_ec = 1 )
    assert 'Presence of lock file indicates competing invocation' in res.out
    run( 'sb --removelock', d )
    assert not lockfile.exists()

def test_pkginfo_case_insensitive( lockproj ):
    #Issue #30: package names are unique when ignoring case, so --pkginfo can
    #be relaxed about casing:
    d = lockproj
    for name in ( 'MyPkg', 'mypkg', 'MYPKG', 'myPKG' ):
        res = run( [ 'sb', '--pkginfo', name ], d )
        assert 'Package name            : MyPkg' in res.out
    res = run( 'sb --pkginfo nosuchpkg', d, expect_ec = 1 )
    assert 'Unknown package "nosuchpkg"' in res.out
