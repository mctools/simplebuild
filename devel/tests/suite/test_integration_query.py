# Tests of the sb query options --grep, --grepi, --grepc, --grepci, --find,
# --findi (and --replace) which search the files of the packages.

import re
import pytest

from sbtestutils import run, run_bash, write_files

pytestmark = pytest.mark.integration

@pytest.fixture
def proj( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'PkgA/pkg.info' : 'package()\n',
        'PkgA/libinc/HistCollection.hh' : ( 'class HistCollection {\n'
                                            '  void addHist( int* h );\n'
                                            '};\n' ),
        'PkgA/libsrc/HistCollection.cc' : ( '#include "PkgA/HistCollection.hh"\n'
                                            'void HistCollection::addHist( int* ) {}\n'
                                            '//histcollection in lower case\n' ),
        'PkgB/pkg.info' : 'package(USEPKG PkgA)\n',
        'PkgB/app_tool/main.cc' : 'int main() { return 0; }//Foo123_Bar here\n',
        'PkgB/data/notes.txt' : 'FOO_BAR and foo_bar\n',
    } )
    return d

def _lines( out ):
    #Output lines without the "sbld:" prefix and whitespace:
    return [ re.sub( r'^sbld:\s*', '', e ).strip() for e in out.splitlines() ]

def test_no_configuration( proj ):
    #The queries only need to find the packages, so they must not create the
    #cache directory (which also means no cmake runs, no lock, etc.):
    d = proj
    for cmd in ( 'sb --grep foo', 'sb --grepc foo', 'sb --find foo',
                 'sb --grepi foo', 'sb --grepci foo', 'sb --findi foo' ):
        res = run( cmd, d )
        assert 'Traceback' not in res.out
    assert not ( d / 'simplebuild_cache' ).exists()

def test_grep_smartcase_and_wildcards( proj ):
    d = proj
    #(the number of matches is the number of lines with matches)
    res = run( 'sb --grep histcollection', d )
    assert 'Found 4 matches' in res.out
    res = run( 'sb --grep HistCollection', d )
    assert 'Found 3 matches' in res.out
    assert 'lower case' not in res.out
    res = run( 'sb --grepi HISTCOLLECTION', d )
    assert 'Found 4 matches' in res.out
    res = run( 'sb --grep Foo*_Bar', d )
    assert 'Found 1 match\n' in res.out
    assert 'PkgB/app_tool/main.cc [L1]' in res.out
    res = run( 'sb --grep foo*_bar', d )
    assert 'Found 2 matches' in res.out
    #A pattern with wildcards also matches the same text taken literally:
    res = run( "sb --grep '( int* )' PkgA PkgB", d )
    assert 'Found 2 matches' in res.out
    res = run( "sb --grep 'RE::^void\\s+Hist'", d )
    assert 'Found 1 match\n' in res.out
    res = run( "sb --grep 'RE::('", d, expect_ec = 1 )
    assert 'Invalid regular expression in pattern "RE::("' in res.out
    #Patterns starting with a dash (issue #74):
    ( d / 'PkgB' / 'data' / 'opts.txt' ).write_text( 'use --force here\n' )
    res = run( 'sb --grep=--force', d )
    assert 'Found 1 match\n' in res.out
    #No matches is not an error:
    res = run( 'sb --grep nosuchtext', d )
    assert 'Found 0 matches' in res.out

def test_grepc( proj ):
    d = proj
    res = run( 'sb --grepc Foo*_Bar', d )
    assert 'PkgB : 1 hit' in _lines( res.out )
    res = run( 'sb --grepci histcollection', d )
    assert 'PkgA : 4 hits' in _lines( res.out )

def test_grep_paths( proj ):
    #Positional arguments limit the search to packages, directories or files:
    d = proj
    res = run( 'sb --grep foo PkgB/data', d )
    assert 'Found 1 match\n' in res.out
    assert 'main.cc' not in res.out
    res = run( 'sb --grep foo PkgB', d )
    assert 'Found 2 matches' in res.out
    res = run( 'sb --grep foo PkgB/app_tool/main.cc', d )
    assert 'Found 1 match\n' in res.out and 'notes.txt' not in res.out
    res = run( 'sb --find PkgB PkgB/data', d )
    assert set( e for e in _lines( res.out ) if e.startswith('PkgB') ) == set( [
        'PkgB/data/', 'PkgB/data/notes.txt' ] )

def test_find( proj ):
    d = proj
    #(the core packages of simplebuild are also searched, so we look only at
    #our own packages)
    res = run( 'sb --find libsrc', d )
    lines = _lines( res.out )
    assert 'PkgA/libsrc/' in lines
    assert 'PkgA/libsrc/HistCollection.cc' in lines
    res = run( "sb --find 'Pkg?/*.cc'", d )
    assert set( e for e in _lines( res.out ) if e.endswith('.cc') ) == set( [
        'PkgA/libsrc/HistCollection.cc', 'PkgB/app_tool/main.cc' ] )
    #Smart case, and the i variant:
    res = run( 'sb --find HISTCOLLECTION', d )
    assert 'Found 0 matches' in res.out
    res = run( 'sb --findi HISTCOLLECTION', d )
    assert 'Found 2 matches' in res.out
    #Package directories:
    res = run( 'sb --find pkgb', d )
    assert 'PkgB/' in _lines( res.out )
    #Search for a file in a given package:
    res = run( 'sb --find PkgB/notes', d )
    assert _lines( res.out ).count( 'PkgB/data/notes.txt' ) == 1

def test_unreadable_files( proj ):
    d = proj
    ( d / 'PkgB' / 'data' / 'broken.txt' ).symlink_to( d / 'nonexisting' )
    res = run( 'sb --grep foo', d )
    assert 'WARNING' in res.out and 'broken.txt' in res.out
    assert 'Found 2 matches' in res.out
    assert 'Traceback' not in res.out

def test_broken_pipe( proj ):
    #Output piped to a command which exits early (e.g. "head") must not give
    #errors:
    d = proj
    res = run_bash( 'set -o pipefail; sb --find Pkg | head -n 2', d )
    assert 'Traceback' not in res.out and 'BrokenPipe' not in res.out
