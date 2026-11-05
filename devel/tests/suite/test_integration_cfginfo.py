# Tests of the inspection of the configuration with sb -s/--summary, sb
# --showcfg and the simplebuild.cfg Python module, which all provide the
# information in the dictionary collected by cfginfo.py.

import json
import pathlib
import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : ( '[bundle]\n'
                              '  name = "proj"\n'
                              '  pkg_root = "./pkgs"\n'
                              '  extdep_root = "./extdeps"\n'
                              '[build]\n'
                              '  mode = "release"\n'
                              '  extra_cflags = "-DPROJ_EXTRA"\n'
                              '  flagsets.fma.extra_cflags = "-DPROJ_FMA"\n' ),
        'extdeps/ExtDep_MyDep.cmake' : ( 'set( HAS_MyDep "1" )\n'
                                         'set( ExtDep_MyDep_VERSION "1.2.3" )\n'
                                         'set( ExtDep_MyDep_COMPILE_FLAGS "" )\n'
                                         'set( ExtDep_MyDep_LINK_FLAGS "" )\n' ),
        'extdeps/ExtDep_MyMissingDep.cmake' : 'set( HAS_MyMissingDep "0" )\n',
        'extdeps/ExtDep_MyUnusedDep.cmake' : 'set( HAS_MyUnusedDep "0" )\n',
        'pkgs/PkgA/pkg.info' : 'package(USEEXT MyDep)\n',
        'pkgs/PkgB/pkg.info' : 'package(USEEXT MyMissingDep)\n',
    } )
    return d

def _json( d, args = '' ):
    res = run( f'sb -s=json {args}', d )
    return json.loads( res.stdout )

def _showcfg( d, key, args = '' ):
    return run( f'sb --showcfg {key} {args}', d ).stdout

def test_no_configuration( proj ):
    #Without -e, the inspection of the configuration does not create the cache
    #directory:
    d = proj
    res = run( 'sb -s', d )
    assert 'build.mode ' in res.stdout and not res.stderr
    assert 'sbld' not in res.stdout
    info = _json( d )
    assert _showcfg( d, '' ) == res.stdout
    assert not ( d / 'simplebuild_cache' ).exists()
    assert info['extdeps'] is None
    assert info['main_cfg_file'] == str( ( d / 'simplebuild.cfg' ).resolve() )
    assert info['bundles'][0]['name'] == 'proj'
    assert info['bundles'][0]['main']
    assert not any( e['main'] for e in info['bundles'][1:] )
    assert info['packages']['total'] >= 3
    b = info['build']
    assert ( b['mode'], b['mode_from'], b['cfg_mode'] ) == ( 'release', 'cfg', 'release' )
    assert b['extra_cflags'] == [ '-DPROJ_EXTRA' ]
    assert b['extra_flags_from'] == 'cfg' and b['flagset'] is None
    assert b['flagsets'] == { 'fma' : { 'extra_cflags' : [ '-DPROJ_FMA' ],
                                        'extra_ldflags' : [] } }
    assert info['variant']['flags'] == []

def test_variants( proj ):
    d = proj
    assert _showcfg( d, 'build.mode', '-d' ) == 'debug\n'
    assert _showcfg( d, 'build.mode_from', '-d' ) == '-d\n'
    assert _showcfg( d, '-g build.mode' ) == 'reldbg\n'
    assert _showcfg( d, 'build.extra_cflags', '-x' ) == ''
    assert _showcfg( d, 'build.extra_flags_from', '-x' ) == '-x\n'
    info = _json( d, '-d -X fma' )
    assert info['build']['flagset'] == 'fma'
    assert info['build']['extra_cflags'] == [ '-DPROJ_FMA' ]
    assert info['variant']['flags'] == [ '-d', '-X', 'fma' ]
    assert info['variant']['blddir'] != _json( d )['variant']['blddir']
    assert _showcfg( d, 'variant.blddir', '-d' ).strip().endswith( 'bld_debug_xf'
        + _showcfg( d, 'variant.blddir' ).strip().split('_xf')[-1] )

def test_unnamed_bundle( proj ):
    d = proj
    ( d / 'simplebuild.cfg' ).write_text( '[bundle]\n  pkg_root = "./pkgs"\n'
                                          '  extdep_root = "./extdeps"\n' )
    #(an unnamed main bundle is referred to as "main"):
    assert _showcfg( d, 'bundles' ).splitlines()[0] == 'main'
    assert _json( d )['bundles'][0]['name'] == 'main'
    run( 'sb', d )
    code = ( 'import simplebuild.cfg as c;'
             'print(c.bundles[0], c.pkgs["PkgA"]["bundle"])' )
    assert run( [ 'sbenv', 'python3', '-c', code ], d ).stdout == 'main main\n'

def test_errors( proj ):
    d = proj
    res = run( 'sb --showcfg nosuchkey', d, expect_ec = 2 )
    assert 'Unknown key "nosuchkey" for --showcfg' in res.stderr
    assert 'build.mode' in res.stderr
    res = run( 'sb -s -X debug', d, expect_ec = 1 )
    assert 'To select the build mode debug, use -d instead' in res.out
    res = run( 'sb -s=xml', d, expect_ec = 2 )
    assert 'Invalid format "xml" for --summary (valid formats are: text, json)' in res.stderr

def test_examine( proj ):
    #With -e, the environment is inspected if needed, so the external
    #dependencies are known (but nothing is built):
    d = proj
    info = _json( d, '-e' )
    ed = info['extdeps']
    assert ed['MyDep'] == { 'present' : True, 'used' : True, 'version' : '1.2.3' }
    assert ed['MyMissingDep'] == { 'present' : False, 'used' : True }
    assert ed['MyUnusedDep'] == { 'present' : False, 'used' : False }
    #(PkgB is disabled due to the missing extdep):
    assert info['packages']['enabled'] == info['packages']['total'] - 1
    assert not ( pathlib.Path( info['variant']['installdir'] ) / 'pkgs' ).exists()
    #The results of the inspection are now used also without -e:
    assert _json( d )['extdeps'] == ed
    assert _showcfg( d, 'extdeps.MyDep.version' ) == '1.2.3\n'
    #(the extdeps provided by simplebuild itself are not used here):
    assert _showcfg( d, 'extdeps.present' ) == 'MyDep 1.2.3\n'
    assert _showcfg( d, 'extdeps.missing' ) == 'MyMissingDep\n'
    unused = _showcfg( d, 'extdeps.unused' ).splitlines()
    assert 'MyUnusedDep' in unused and 'MyDep' not in unused

def _cachedir_lines( out ):
    #The lines of the cache directory overview at the end of the text summary:
    lines = out.split( '\nCache directories in ' )[1].splitlines()[1:]
    return [ e.split() for e in lines ]

def test_cachedirs( proj ):
    #The text summary ends with an overview of the cache directories of all
    #build variants (which is not part of the configuration info):
    d = proj
    assert 'Cache directories' not in run( 'sb -s', d ).stdout
    for args in ( '-e', '-d -X fma -e', '-g -x -e' ):
        run( f'sb -s {args}', d )
    out = run( 'sb -s', d ).stdout
    assert 'Cache directories' not in run( 'sb -s=json', d ).stdout
    assert _showcfg( d, '' ) == out
    lines = _cachedir_lines( out )
    #(flag set names first, the size in the next to last columns):
    assert lines[0][:3] == [ 'fma', 'debug', 'extra_cflags=-DPROJ_FMA' ]
    assert lines[1][0] == 'reldbg' and lines[1][2] in ( 'B', 'kB', 'MB', 'GB' )
    assert lines[2][:2] == [ 'release', 'extra_cflags=-DPROJ_EXTRA' ]
    assert len( lines ) == 3
    assert lines[2][-1] == 'current' and lines[0][-1] != 'current'
    for e in lines:
        assert e[-1 if e[-1] != 'current' else -2] in ( 'B', 'kB', 'MB', 'GB' )
    out = run( 'sb -s -d -X fma', d ).stdout
    assert _cachedir_lines( out )[0][-1] == 'current'

def test_python_module( proj ):
    #Each build installs the information for use from Python via the
    #simplebuild.cfg module:
    d = proj
    run( 'sb', d )
    info = _json( d )
    installed = json.loads( ( pathlib.Path( info['variant']['installdir'] )
                              / 'cfginfo.json' ).read_text() )
    assert installed == info
    code = ( 'import simplebuild.cfg as c, json;'
             'print(json.dumps(dict(info=c.info, build_mode=c.build_mode,'
             ' extra_cflags=c.extra_cflags, extra_ldflags=c.extra_ldflags,'
             ' flagset=c.flagset, bundles=c.bundles,'
             ' main_cfg_file=str(c.main_cfg_file), extdeps=c.extdeps,'
             ' pkgbundles={k:v["bundle"] for k,v in c.pkgs.items()})))' )
    res = run( [ 'sbenv', 'python3', '-c', code ], d )
    py = json.loads( res.stdout )
    assert py['info'] == installed
    assert py['build_mode'] == 'release'
    assert py['extra_cflags'] == [ '-DPROJ_EXTRA' ]
    assert py['extra_ldflags'] == [] and py['flagset'] is None
    assert py['bundles'][0] == 'proj' and 'core' in py['bundles']
    assert py['main_cfg_file'] == info['main_cfg_file']
    assert py['extdeps']['MyDep']['version'] == '1.2.3'
    assert py['pkgbundles']['PkgA'] == 'proj'
    assert py['pkgbundles']['PkgB'] == 'proj'
    assert py['pkgbundles']['Core'] == 'core'

def _cachedir_names( d ):
    out = run( 'sb -s', d ).stdout
    if 'Cache directories' not in out:
        return []
    return [ ' '.join( e[:-2] if e[-1] != 'current' else e[:-3] )
             for e in _cachedir_lines( out ) ]

def test_clean_variants( proj ):
    #"sb -c NAME" removes the cache directories of the variants with the build
    #mode or flag set NAME:
    d = proj
    for args in ( '', '-d', '-X fma', '-d -X fma', '-g -x' ):
        run( f'sb -s -e {args}', d )
    assert _cachedir_names( d ) == [ 'fma debug extra_cflags=-DPROJ_FMA',
                                     'fma release extra_cflags=-DPROJ_FMA',
                                     'debug extra_cflags=-DPROJ_EXTRA',
                                     'reldbg',
                                     'release extra_cflags=-DPROJ_EXTRA' ]
    res = run( 'sb -c nosuchname', d, expect_ec = 2 )
    assert ( 'Invalid name "nosuchname" given to --clean (must be a build mode'
             ' or the name of a flag set: debug, release, reldbg, fma)' ) in res.stderr
    res = run( 'sb -c fma', d )
    assert res.out.count( 'Removed cache directories' ) == 2
    assert _cachedir_names( d ) == [ 'debug extra_cflags=-DPROJ_EXTRA',
                                     'reldbg',
                                     'release extra_cflags=-DPROJ_EXTRA' ]
    run( 'sb -c debug', d )
    assert _cachedir_names( d ) == [ 'reldbg', 'release extra_cflags=-DPROJ_EXTRA' ]
    assert 'Nothing to clean' in run( 'sb -c debug', d ).out
    #The cache dir of the selected variant is not left behind when it did not
    #exist already:
    run( 'sb -c release', d )
    assert _cachedir_names( d ) == [ 'reldbg' ]
    run( 'sb -c reldbg', d )
    assert _cachedir_names( d ) == []
    assert not any( ( d / 'simplebuild_cache' ).glob( 'bld*' ) )
