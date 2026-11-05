# Tests of sb --exportcmds, which exports the compilation commands of all
# packages in the JSON format of CMAKE_EXPORT_COMPILE_COMMANDS.

import json
import pytest

from sbtestutils import run, write_files, n_compiled

pytestmark = pytest.mark.integration

def test_exportcmds( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\n  name = "proj"\n',
        'PkgA/pkg.info' : 'package()\n',
        'PkgA/libinc/A.hh' : 'int a();\n',
        'PkgA/libsrc/A.cc' : '#include "PkgA/A.hh"\nint a() { return 1; }\n',
        'PkgB/pkg.info' : 'package(USEPKG PkgA)\n',
        'PkgB/app_foo/main.cc' : '#include "PkgA/A.hh"\nint main() { return a() == 1 ? 0 : 1; }\n',
    } )
    def ourfiles( f ):
        return sorted( str(e['file']).split('/proj/')[1]
                       for e in json.loads( ( d / f ).read_text() )
                       if '/proj/' in e['file'] )
    #From scratch:
    run( 'sb --exportcmds cmds1.json', d )
    assert ourfiles( 'cmds1.json' ) == [ 'PkgA/libsrc/A.cc', 'PkgB/app_foo/main.cc' ]
    #After a build, exporting the commands does not require anything to be
    #rebuilt, and gives the same result:
    res = run( 'sb --exportcmds cmds2.json', d )
    assert n_compiled( res.out ) == 0
    assert 'complete rebuild' not in res.out
    assert ( json.loads( ( d / 'cmds1.json' ).read_text() )
             == json.loads( ( d / 'cmds2.json' ).read_text() ) )
    #And afterwards, a build does not rebuild anything either:
    res = run( 'sb', d )
    assert n_compiled( res.out ) == 0
    #Existing files are not overwritten:
    res = run( 'sb --exportcmds cmds2.json', d, expect_ec = 2 )
    assert 'File already exists' in res.out
