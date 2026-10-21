# Package filters, example projects, and other project-level features. This
# repeats tests originally carried out directly in the basictest workflow.

import shutil

import pytest

from sbtestutils import reporoot, run, write_files

pytestmark = pytest.mark.integration

def test_pkgfilter( tmp_path ):
    d = tmp_path / 'myproj_pkgfilter'
    d.mkdir()
    cachedir = tmp_path / 'somecachedir'
    run( [ 'sb', '--init', 'core_val', f'CACHEDIR::{cachedir}',
           'PKGFILTER::Core*', 'PKGFILTER::!CoreLink*' ], d )
    run( "sb -t --testexcerpts=100 --requirepkg 'Core,CoreTests'", d )
    assert cachedir.is_dir()
    res = run( 'sb --requirepkg CoreLinkTests', d, expect_ec = None )
    assert res.ec != 0
    res = run( 'sbenv which sb_corelinktests_test', d, expect_ec = None )
    assert res.ec != 0
    #Clean removes the build output, but not the custom cachedir itself:
    run( 'sb -c', d )
    assert cachedir.is_dir() and not any( cachedir.iterdir() )

def copy_example_project( name, dest ):
    src = reporoot / 'devel' / name
    shutil.copytree( src, dest, symlinks = True,
                     ignore = shutil.ignore_patterns( 'autogen_dynpkgs',
                                                      'simplebuild_cache' ) )

def test_dynamic_generator( tmp_path ):
    d = tmp_path / 'myproj_dyngen'
    copy_example_project( 'example_project_dynamic', d )
    run( 'sb -t --requirepkg MyPkg', d )
    run( 'sbenv sb_mypkg_testbla', d )

def test_custom_extdeps( tmp_path ):
    d = tmp_path / 'myproj_extdep'
    copy_example_project( 'example_project_custom_extdeps', d )
    run( 'sb -t --requirepkg MyPkg', d )

def test_scripts_data_and_python( tmp_path ):
    #A package with scripts, data, python modules, and a failing test:
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/scripts/hello' : '#!/usr/bin/env python3\nimport MyPkg.mymod\nMyPkg.mymod.hello()\n',
        'MyPkg/python/mymod.py' : 'def hello():\n    print("hello from mymod")\n',
        'MyPkg/data/somefile.txt' : 'somedata\n',
        'MyPkg/scripts/testfail' : '#!/usr/bin/env python3\nraise SystemExit(1)\n',
    } )
    for f in ( 'hello', 'testfail' ):
        ( d / 'MyPkg' / 'scripts' / f ).chmod( 0o755 )
    res = run( 'sb -t', d, expect_ec = 73 )#73 means tests failed
    assert 'sb_mypkg_testfail' in res.out
    res = run( 'sbenv sb_mypkg_hello', d )
    assert res.stdout.strip() == 'hello from mymod'
    res = run( 'sbenv sb_core_finddata MyPkg somefile.txt', d )
    assert res.stdout.strip().endswith( 'somefile.txt' )

def test_compilation_failure( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'MyPkg/pkg.info' : 'package()\n',
        'MyPkg/app_bad/main.cc' : 'this is not c++\n',
    } )
    res = run( 'sb', d, expect_ec = None )
    assert res.ec not in ( 0, 73 )
    assert 'Build problems encountered' in res.out
