import pytest

from _simple_build_system import cfginfo

pytestmark = pytest.mark.unit

def _example():
    return {
        'main_cfg_file' : '/proj/simplebuild.cfg',
        'bundles' : [ { 'name' : 'proj', 'cfgfile' : '/proj/simplebuild.cfg',
                        'pkg_root' : '/proj', 'main' : True },
                      { 'name' : 'core', 'cfgfile' : '/core/simplebuild.cfg',
                        'pkg_root' : '/core', 'main' : False } ],
        'pkgsearchpath' : [ '/proj', '/core' ],
        'packages' : { 'total' : 3, 'enabled' : 2, 'filter' : [] },
        'build' : { 'mode' : 'debug', 'mode_from' : '-d', 'cfg_mode' : 'release',
                    'extra_cflags' : [ '-O1', '-g' ], 'extra_ldflags' : [],
                    'extra_flags_from' : 'cfg', 'flagset' : None,
                    'flagsets' : { 'fma' : { 'extra_cflags' : [ '-mfma' ],
                                             'extra_ldflags' : [] } },
                    'max_cachedirs' : 5 },
        'variant' : { 'flags' : [ '-d' ], 'cachedir' : '/proj/simplebuild_cache',
                      'blddir' : '/proj/simplebuild_cache/bld_debug',
                      'installdir' : '/proj/simplebuild_cache/install_debug' },
        'extdeps' : { 'DL' : { 'present' : True, 'used' : True, 'version' : '-' },
                      'Geant4' : { 'present' : True, 'used' : True, 'version' : '11.4.3' },
                      'ROOT' : { 'present' : False, 'used' : True },
                      'HDF5' : { 'present' : False, 'used' : False } },
    }

def _parse_text( text ):
    #Parse "KEY : VALUE" lines (with lists continuing on the next lines):
    res, key = {}, None
    for line in text.splitlines():
        if not line.strip():
            key = None
            continue
        if line.startswith(' '):
            assert key is not None
            res[key].append( line.strip() )
            continue
        k, v = line.split(' : ',1) if ' : ' in line else ( line.rstrip(' :'), '' )
        key = k.strip()
        res[key] = [ v.strip() ] if v.strip() else []
    return res

def test_text_summary():
    d = _example()
    text = cfginfo.format_text( d )
    assert 'sbld' not in text and '(' not in text
    #The separators are aligned:
    assert len( set( line.index(' : ') for line in text.splitlines()
                     if ' : ' in line ) ) == 1
    p = _parse_text( text )
    assert p['bundles'] == [ 'proj', 'core' ]
    assert p['build.mode'] == [ 'debug' ]
    assert p['build.mode_from'] == [ '-d' ]
    assert p['build.extra_cflags'] == [ '-O1', '-g' ]
    assert p['build.extra_ldflags'] == []
    assert p['build.flagset'] == []
    assert p['build.flagsets'] == [ 'fma' ]
    assert p['packages.enabled'] == [ '2' ]
    assert p['variant.flags'] == [ '-d' ]
    assert p['extdeps.present'] == [ 'DL', 'Geant4 11.4.3' ]
    assert p['extdeps.missing'] == [ 'ROOT' ]
    assert p['extdeps.unused'] == [ 'HDF5' ]

def test_text_summary_unknown_extdeps():
    d = _example()
    d['extdeps'] = None
    text = cfginfo.format_text( d )
    assert _parse_text( text )['extdeps.present'] == []
    assert 'run "sb -s -e"' in text

def test_lookup():
    d = _example()
    assert cfginfo.lookup( d, 'build.mode' ) == 'debug\n'
    assert cfginfo.lookup( d, 'build.extra_cflags' ) == '-O1\n-g\n'
    assert cfginfo.lookup( d, 'build.extra_ldflags' ) == ''
    assert cfginfo.lookup( d, 'build.flagset' ) == '\n'
    assert cfginfo.lookup( d, 'bundles' ) == 'proj\ncore\n'
    assert cfginfo.lookup( d, 'extdeps.missing' ) == 'ROOT\n'
    assert cfginfo.lookup( d, 'extdeps.Geant4.version' ) == '11.4.3\n'
    assert cfginfo.lookup( d, 'extdeps.Geant4.present' ) == 'true\n'
    assert cfginfo.lookup( d, 'bundles.1.pkg_root' ) == '/core\n'
    assert cfginfo.lookup( d, 'build.flagsets.fma.extra_cflags' ) == '-mfma\n'
    assert cfginfo.lookup( d, 'variant.flags' ) == '-d\n'
    #Tables give KEY : VALUE lines:
    out = cfginfo.lookup( d, 'extdeps.Geant4' )
    assert _parse_text( out ) == { 'extdeps.Geant4.present' : [ 'true' ],
                                   'extdeps.Geant4.used' : [ 'true' ],
                                   'extdeps.Geant4.version' : [ '11.4.3' ] }
    for k in ( 'nokey', 'build.nokey', 'build.mode.x', 'bundles.7' ):
        assert cfginfo.lookup( d, k ) is None

def test_valid_keys():
    d = _example()
    keys = cfginfo.valid_keys( d )
    assert keys[0] == 'main_cfg_file'
    assert len( keys ) == len( set( keys ) )
    for k in ( 'build.mode', 'extdeps.present', 'extdeps.Geant4.version',
               'bundles.0.main' ):
        assert k in keys
    for k in keys:
        assert cfginfo.lookup( d, k ) is not None

def test_json():
    import json
    d = _example()
    assert json.loads( cfginfo.format_json( d ) ) == d
