#!/usr/bin/env python3

# Test of build variants: the build.extra_cflags, build.extra_ldflags, and
# build.max_cachedirs cfg options, the -d/-r/-g/-x flags of sb, sbrun, and
# sbenv, and the management of cache directories for the various variants.
#
# Run from an empty directory, with simplebuild installed (it uses the sb,
# sbrun, sbenv, and unwrapped_simplebuild commands from PATH).

import os
import pathlib
import re
import shlex
import subprocess
import sys

#The tests rely on the default location of the cache directories:
os.environ.pop( 'SIMPLEBUILD_CACHE_ROOT', None )

workdir = pathlib.Path('sbtest_build_variants').absolute()
cachedir = workdir / 'simplebuild_cache'

def fail( msg ):
    raise SystemExit(f'\nTEST FAILURE: {msg}')

def run( cmd, *, expect_ec = 0, cwd = None ):
    """Run command, check exit code, and return combined stdout+stderr."""
    print(f'\n>>> {cmd}', flush = True)
    env = os.environ.copy()
    for k in list(env.keys()):
        if k.startswith('SBLD_') or k == '_SIMPLEBUILD_CURRENT_ENV':
            del env[k]
    p = subprocess.run( shlex.split(cmd), cwd = cwd or workdir, env = env,
                        capture_output = True, check = False )
    out = p.stdout.decode() + p.stderr.decode()
    print(out, flush = True)
    if expect_ec is not None and p.returncode != expect_ec:
        fail(f'Command {cmd} gave exit code {p.returncode}'
             f' (expected {expect_ec})')
    return out

def run_split( cmd ):
    """Run command, and return stdout and stderr separately."""
    print(f'\n>>> {cmd}', flush = True)
    p = subprocess.run( shlex.split(cmd), cwd = workdir,
                        capture_output = True, check = False )
    return p.returncode, p.stdout.decode(), p.stderr.decode()

def require( cond, msg ):
    if not cond:
        fail(msg)

def require_in( substr, txt ):
    require( substr in txt, f'Did not find expected text: "{substr}"' )

def require_not_in( substr, txt ):
    require( substr not in txt, f'Found unexpected text: "{substr}"' )

def summary_line( out, label ):
    for line in out.splitlines():
        if re.match( r'^sbld:\s+' + re.escape(label) + r'\s+:', line ):
            return line.split(':',2)[2].strip()
    return None

def n_compiled( out ):
    return sum( 1 for line in out.splitlines()
                if line.strip().startswith('Building ') )

def cachedir_names():
    """Names of the build variant directories in the cache dir."""
    if not cachedir.is_dir():
        return []
    names = sorted( f.name for f in cachedir.iterdir() )
    #The cache dir also records the location of the simplebuild.cfg file:
    if names and 'simplebuild_cfg_path.txt' not in names:
        fail('Missing simplebuild_cfg_path.txt in cache dir')
    return [ n for n in names if n != 'simplebuild_cfg_path.txt' ]

def write_cfg( build_section_lines ):
    lines = [ '[bundle]', "  name = 'variantstest'", '[build]' ]
    lines += [ '  '+e for e in build_section_lines ]
    ( workdir / 'simplebuild.cfg' ).write_text( '\n'.join(lines) + '\n' )

def app_output( out ):
    """Extract output line from our test app"""
    lines = [ e for e in out.splitlines() if e.startswith('VARIANTSTEST ') ]
    require( len(lines) == 1, 'Did not get expected output from test app' )
    return lines[0]

def setup_project():
    require( not workdir.exists(), f'{workdir} already exists' )
    workdir.mkdir()
    pkg = workdir / 'MyPkg'
    ( pkg / 'libsrc' ).mkdir( parents = True )
    ( pkg / 'libinc' ).mkdir()
    ( pkg / 'app_test' ).mkdir()
    ( pkg / 'pkg.info' ).write_text('package()\n')
    ( pkg / 'libinc' / 'Foo.hh' ).write_text('int foo();\nbool isdebug();\n')
    ( pkg / 'libsrc' / 'Foo.cc' ).write_text(
        '#include "MyPkg/Foo.hh"\n'
        '#ifndef VARIANTSTEST_CFLAG\n'
        '#  define VARIANTSTEST_CFLAG 0\n'
        '#endif\n'
        'int foo() { return VARIANTSTEST_CFLAG; }\n'
        '#ifdef NDEBUG\n'
        'bool isdebug() { return false; }\n'
        '#else\n'
        'bool isdebug() { return true; }\n'
        '#endif\n' )
    ( pkg / 'app_test' / 'main.cc' ).write_text(
        '#include "MyPkg/Foo.hh"\n'
        '#include <cstdio>\n'
        'int main( int argc, char** argv ) {\n'
        '  std::printf("VARIANTSTEST cflag=%i debug=%i args:",\n'
        '              foo(), (int)isdebug() );\n'
        '  for ( int i = 1; i < argc; ++i )\n'
        '    std::printf(" %s",argv[i]);\n'
        '  std::printf("\\n");\n'
        '  return 0;\n'
        '}\n' )

def makefile_content( blddirname ):
    return ( cachedir / blddirname / 'makefiles' / 'Makefile' ).read_text()

def find_xf_name( prefix ):
    names = [ e for e in cachedir_names()
              if re.match( '^' + prefix + r'_xf[0-9a-f]{10}$', e ) ]
    require( len(names) == 1, f'Did not find exactly one {prefix}_xf* dir' )
    return names[0]

def test_cfg_validation():
    print('\n========== Testing cfg validation ==========')
    for bad, errmsg in [ ( "extra_cflags = '-DFOO=\"a b\"'", 'Unsupported flag' ),
                         ( "extra_cflags = ['-O2', '$(FOO)']", 'Unsupported flag' ),
                         ( "extra_ldflags = '-Wl,-rpath,$ORIGIN'", 'Unsupported flag' ),
                         ( "extra_cflags = '-DFOO=(1)'", 'Unsupported flag' ),
                         ( "extra_cflags = 'unbalanced \"quote'", 'No closing quotation' ),
                         ( "extra_cflags = 17", 'expected string or list of strings' ),
                         ( "extra_cflags = ['-O2', 17]", 'expected string or list of strings' ),
                         ( "max_cachedirs = 0", 'must be an integer from 1 to 20' ),
                         ( "max_cachedirs = 21", 'must be an integer from 1 to 20' ),
                         ( "max_cachedirs = true", 'must be an integer from 1 to 20' ),
                         ( "max_cachedirs = '5'", 'must be an integer from 1 to 20' ) ]:
        write_cfg( [ bad ] )
        out = run( 'sb', expect_ec = 1 )
        require_in( errmsg, out )
        if errmsg == 'Unsupported flag':
            require_in( 'https://github.com/mctools/simplebuild/issues', out )
    require( not cachedir.exists(), 'Cache dir created despite cfg errors' )

def test_flag_parsing_equivalence():
    print('\n========== Testing string vs. list values ==========')
    #Different ways of specifying the same flags must give the same variant:
    names = []
    for v in ( "'-O2 -DVARIANTSTEST_CFLAG=7'",
               "['-O2','-DVARIANTSTEST_CFLAG=7']",
               "['-O2 -DVARIANTSTEST_CFLAG=7']",
               "[' -O2', '', '-DVARIANTSTEST_CFLAG=7 ']" ):
        write_cfg( [ f'extra_cflags = {v}' ] )
        out = run( 'sb --env-setup' )
        m = re.search( r'SBLD_INSTALL_PREFIX=(\S+)', out )
        require( m, 'No SBLD_INSTALL_PREFIX in --env-setup output' )
        names.append( pathlib.Path(m.group(1).strip('\'"')).name )
    require( len(set(names)) == 1, f'Got different variants: {names}' )
    require( re.match( r'^install_xf[0-9a-f]{10}$', names[0] ),
             f'Unexpected install dir name: {names[0]}' )

def test_variants():
    print('\n========== Testing build variants ==========')
    write_cfg( [ "extra_cflags = '-ffp-contract=off -DVARIANTSTEST_CFLAG=7'",
                 "extra_ldflags = ['-Wl,-rpath,/variantstest/dummy']" ] )

    #Default variant (release mode with extra flags):
    out = run( 'sb' )
    require_in( 'sbld WARNING: The simplebuild cfg file specifies extra flags'
                ' (extra_cflags: -ffp-contract=off -DVARIANTSTEST_CFLAG=7'
                '  extra_ldflags: -Wl,-rpath,/variantstest/dummy).'
                ' Use "sb -x" to build without them.', out )
    require( summary_line( out, 'Build mode' ) == 'release',
             'Wrong build mode in summary' )
    require( summary_line( out, 'Extra flags' )
             == ( 'extra_cflags: -ffp-contract=off -DVARIANTSTEST_CFLAG=7'
                  '  extra_ldflags: -Wl,-rpath,/variantstest/dummy' ),
             'Wrong extra flags in summary' )
    xf = find_xf_name( 'bld' )
    require( cachedir_names() == sorted( [ xf, 'install' + xf[3:] ] ),
             f'Unexpected cache dir content: {cachedir_names()}' )
    #Flags must be in the generated Makefile, after all other flags:
    mf = makefile_content( xf )
    for line in mf.splitlines():
        if line.startswith('CFLAGSLANG_SHLIB_cxx :='):
            require( line.endswith(' -ffp-contract=off -DVARIANTSTEST_CFLAG=7'),
                     'Extra cflags not at the end of the compile flags' )
        if line.startswith('LDFLAGSLANG_cxx :='):
            require( line.endswith(' -Wl,-rpath,/variantstest/dummy'),
                     'Extra ldflags not at the end of the link flags' )
    require_in( '-Wl,-rpath,/variantstest/dummy', mf )
    require_in( 'extra_cflags: -ffp-contract=off -DVARIANTSTEST_CFLAG=7',
                ( cachedir / xf / 'extra_flags.txt' ).read_text() )
    out = run( 'sbenv sb_mypkg_test' )
    require( app_output( out ) == 'VARIANTSTEST cflag=7 debug=0 args:',
             'Wrong app output' )

    #Rebuilding the same variant must not recompile anything:
    out = run( 'sb' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )

    #Ignoring the extra flags:
    out = run( 'sb -x' )
    require_not_in( 'WARNING', out )
    require( summary_line( out, 'Build mode' ) == 'release',
             'Wrong build mode in summary' )
    require( summary_line( out, 'Extra flags' ) == '<ignored due to -x>',
             'Wrong extra flags in summary' )
    require( 'bld' in cachedir_names() and 'install' in cachedir_names(),
             'Missing bld+install dirs' )
    require_not_in( 'variantstest/dummy', makefile_content( 'bld' ) )
    out = run( 'sbenv -x sb_mypkg_test' )
    require( app_output( out ) == 'VARIANTSTEST cflag=0 debug=0 args:',
             'Wrong app output' )

    #Switching back must reuse the cached build:
    out = run( 'sb' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )
    out = run( 'sb -x' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )

    #Modes:
    out = run( 'sb -d' )
    require( summary_line( out, 'Build mode' ) == 'debug (due to -d)',
             'Wrong build mode in summary' )
    find_xf_name( 'bld_debug' )
    out = run( 'sb -r' )#same as cfg file, so no annotation
    require( summary_line( out, 'Build mode' ) == 'release',
             'Wrong build mode in summary' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )
    for flags in ( '-gx', '-xg', '-x -g', '-g -x' ):
        out = run( f'sb {flags}' )
        require( summary_line( out, 'Build mode' ) == 'reldbg (due to -g)',
                 'Wrong build mode in summary' )
        require( summary_line( out, 'Extra flags' ) == '<ignored due to -x>',
                 'Wrong extra flags in summary' )
    require( 'bld_reldbg' in cachedir_names(), 'Missing bld_reldbg dir' )
    #Mode flags can be combined with other short flags:
    out = run( 'sb -tdx' )
    require( summary_line( out, 'Build mode' ) == 'debug (due to -d)',
             'Wrong build mode in summary' )
    require( 'bld_debug' in cachedir_names(), 'Missing bld_debug dir' )

    #Conflicting modes:
    for flags in ( '-dr', '-d -g', '-rg', '-xdg' ):
        out = run( f'sb {flags}', expect_ec = 2 )
        require_in( 'not allowed with argument', out )

    #A mode in the cfg file is overridden, and a flag selecting the same mode
    #is not shown as an override:
    write_cfg( [ "mode = 'debug'",
                 "extra_cflags = '-ffp-contract=off -DVARIANTSTEST_CFLAG=7'",
                 "extra_ldflags = ['-Wl,-rpath,/variantstest/dummy']" ] )
    out = run( 'sb -x' )
    require( summary_line( out, 'Build mode' ) == 'debug',
             'Wrong build mode in summary' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )
    out = run( 'sb -d -x' )
    require( summary_line( out, 'Build mode' ) == 'debug',
             'Wrong build mode in summary' )
    out = run( 'sb -r' )
    require( summary_line( out, 'Build mode' ) == 'release (due to -r)',
             'Wrong build mode in summary' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )
    write_cfg( [ "extra_cflags = '-ffp-contract=off -DVARIANTSTEST_CFLAG=7'",
                 "extra_ldflags = ['-Wl,-rpath,/variantstest/dummy']" ] )

    #No extra flags in the cfg file, so no Extra flags line unless -x:
    write_cfg( [] )
    out = run( 'sb' )
    require( summary_line( out, 'Extra flags' ) is None,
             'Unexpected Extra flags line in summary' )
    require( n_compiled( out ) == 0, 'Unexpected recompilation' )
    out = run( 'sb -x' )
    require( summary_line( out, 'Extra flags' ) == '<ignored due to -x>',
             'Wrong extra flags in summary' )
    write_cfg( [ "extra_cflags = '-ffp-contract=off -DVARIANTSTEST_CFLAG=7'",
                 "extra_ldflags = ['-Wl,-rpath,/variantstest/dummy']" ] )

def test_launchers():
    print('\n========== Testing sbrun and sbenv ==========')
    #Leading flags are for sbrun/sbenv, everything after the program is passed
    #on to the program:
    for cmd, expected in [
            ( 'sbenv sb_mypkg_test', 'cflag=7 debug=0 args:' ),
            ( 'sbenv sb_mypkg_test -x -d', 'cflag=7 debug=0 args: -x -d' ),
            ( 'sbenv -x sb_mypkg_test -d', 'cflag=0 debug=0 args: -d' ),
            ( 'sbenv -d sb_mypkg_test', 'cflag=7 debug=1 args:' ),
            ( 'sbenv -xd sb_mypkg_test a b', 'cflag=0 debug=1 args: a b' ),
            ( 'sbenv -d -x sb_mypkg_test', 'cflag=0 debug=1 args:' ),
            ( 'sbenv -x -r sb_mypkg_test', 'cflag=0 debug=0 args:' ),
            ( 'sbrun sb_mypkg_test -g', 'cflag=7 debug=0 args: -g' ),
            ( 'sbrun -xd sb_mypkg_test -x', 'cflag=0 debug=1 args: -x' ),
            ( 'sbrun -g sb_mypkg_test', 'cflag=7 debug=0 args:' ) ]:
        out = run( cmd )
        require( app_output( out ) == f'VARIANTSTEST {expected}',
                 f'Wrong app output from "{cmd}"' )
    find_xf_name( 'bld_reldbg' )#created by sbrun -g

    #sbrun is quiet (no warnings about extra flags):
    out = run( 'sbrun sb_mypkg_test' )
    require_not_in( 'WARNING', out )

    #Errors and help:
    out = run( 'sbrun -dr sb_mypkg_test', expect_ec = 2 )
    require_in( 'not allowed with argument', out )
    out = run( 'sbenv -x', expect_ec = 2 )
    require_in( 'missing program to run', out )
    out = run( 'sbenv -q sb_mypkg_test', expect_ec = 2 )
    out = run( 'sbenv', expect_ec = 111 )
    require_in( 'Usage:', out )
    for cmd in ( 'sbenv -h', 'sbrun --help' ):
        out = run( cmd )
        require_in( '[-d|-r|-g] [-x] <program> [args]', out )

def test_determinism():
    print('\n========== Testing determinism ==========')
    #The variant only depends on the flags of the current command, never on
    #previous commands:
    for prev in ( 'sb -d', 'sb -x', 'sb -gx', 'sb' ):
        run( prev )
        out = run( 'sbenv sb_mypkg_test' )
        require( app_output( out ) == 'VARIANTSTEST cflag=7 debug=0 args:',
                 f'sbenv output depends on previous command ({prev})' )
        out = run( 'sb --env-setup' )
        require_in( 'install_xf', out )

def test_env_setup():
    print('\n========== Testing --env-setup ==========')
    out = run( 'sb -d --env-setup' )
    require( re.search( r'SBLD_INSTALL_PREFIX=\S*/install_debug_xf[0-9a-f]{10}\b', out ),
             'Wrong env setup for -d' )
    out = run( 'sb --env-setup -x' )
    require( re.search( r'SBLD_INSTALL_PREFIX=\S*/simplebuild_cache/install\b', out ),
             'Wrong env setup for -x' )
    out = run( 'sb -t --env-setup', expect_ec = 1 )
    require_in( 'Do not use --env-setup with other arguments', out )
    out = run( 'sb -d --env-unsetup', expect_ec = 1 )
    require_in( 'Do not use --env-unsetup with other arguments', out )

    #The hidden flag used by the shell snippet after builds:
    ec, out, err = run_split( 'unwrapped_simplebuild --env-setup-after-build -q -tdx' )
    require( ec == 0 and not err, 'Unexpected failure' )
    require( re.search( r'SBLD_INSTALL_PREFIX=\S*/install_debug\b', out ),
             'Wrong env setup after build' )
    for bad in ( '-h', '--help', '-dr', '--nosuchflag' ):
        ec, out, err = run_split( f'unwrapped_simplebuild --env-setup-after-build {bad}' )
        require( ec == 0 and not out and not err,
                 f'Unexpected output after build with {bad}' )

    #The flag used by old versions of the shell snippet:
    ec, out, err = run_split( 'unwrapped_simplebuild --env-setup-silent-fail' )
    require( ec != 0, 'Old shell snippet did not cause an error' )
    require( not out, 'Old shell snippet error emitted output on stdout' )
    require_in( 'outdated version of the "sb" shell function', err )
    require_in( 'unwrapped_simplebuild --env-setup-after-build', err )

def test_max_cachedirs():
    print('\n========== Testing build.max_cachedirs ==========')
    #Start from scratch, and create 5 cache dirs in a known order:
    import time
    run( 'sb -c' )
    require( not cachedir.exists(), 'Default cache dir not removed' )
    for flags in ( '-g', '-gx', '-x', '-d', '-dx' ):
        run( f'sb {flags}' )
        time.sleep(1.1)#make sure the last_used order is unambiguous
    print('Cache dirs:',cachedir_names())
    reldbg_xf = find_xf_name( 'bld_reldbg' )
    debug_xf = find_xf_name( 'bld_debug' )
    require( cachedir_names() == sorted( [ 'bld', 'install',
                                           'bld_debug', 'install_debug',
                                           'bld_reldbg', 'install_reldbg',
                                           reldbg_xf, 'install'+reldbg_xf[3:],
                                           debug_xf, 'install'+debug_xf[3:] ] ),
             f'Unexpected cache dirs: {cachedir_names()}' )
    #Add a dir without fingerprint file, which must never be removed (nor
    #counted):
    ( cachedir / 'bld_reldbg_xf0123456789' ).mkdir()
    #Make the oldest cache dir appear locked by another process:
    ( cachedir / reldbg_xf / '.lock' ).write_text('999999999')
    write_cfg( [ "extra_cflags = '-ffp-contract=off -DVARIANTSTEST_CFLAG=7'",
                 "extra_ldflags = ['-Wl,-rpath,/variantstest/dummy']",
                 "max_cachedirs = 3" ] )
    out = run( 'sb' )
    print('Cache dirs:',cachedir_names())
    #Kept: The current, the locked one, the most recently used one (-dx), and
    #the one without fingerprint:
    xf = find_xf_name( 'bld' )
    expected = sorted( [ xf, 'install'+xf[3:],
                         reldbg_xf, 'install'+reldbg_xf[3:],
                         'bld_debug', 'install_debug',
                         'bld_reldbg_xf0123456789' ] )
    require( cachedir_names() == expected,
             f'Unexpected cache dirs: {cachedir_names()}' )
    for removed in ( 'bld_reldbg+install_reldbg', 'bld+install',
                     f'{debug_xf}+install{debug_xf[3:]}' ):
        require_in( 'Removed least recently used cache directories'
                    f' (build.max_cachedirs=3): {removed}', out )
    #The current one must not be removed even with max_cachedirs=1:
    write_cfg( [ "max_cachedirs = 1" ] )
    out = run( 'sbrun -d sb_mypkg_test' )
    require( app_output( out ) == 'VARIANTSTEST cflag=0 debug=1 args:',
             'Wrong app output' )
    require( cachedir_names() == sorted( [ 'bld_debug', 'install_debug',
                                           reldbg_xf, 'install'+reldbg_xf[3:],
                                           'bld_reldbg_xf0123456789' ] ),
             f'Unexpected cache dirs: {cachedir_names()}' )
    ( cachedir / reldbg_xf / '.lock' ).unlink()

    #Clean must remove everything except the dir without fingerprint:
    out = run( 'sb -c' )
    require_in( 'Removing temporary cache directories.', out )
    require_in( 'Not removing cache directories', out )
    require( cachedir_names() == [ 'bld_reldbg_xf0123456789' ],
             f'Unexpected cache dirs after clean: {cachedir_names()}' )
    ( cachedir / 'bld_reldbg_xf0123456789' ).rmdir()
    out = run( 'sb -c' )
    require_in( 'Nothing to clean', out )
    require( not cachedir.exists(), 'Default cache dir not removed' )

def main():
    setup_project()
    test_cfg_validation()
    test_flag_parsing_equivalence()
    test_variants()
    test_launchers()
    test_determinism()
    test_env_setup()
    test_max_cachedirs()
    print('\nAll build variant tests completed successfully!')

if __name__ == '__main__':
    main()
    sys.exit(0)
