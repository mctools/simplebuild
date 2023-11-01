#!/usr/bin/env python3

__author__ = 'Thomas Kittelmann'

import argparse
import pathlib
import os
import os.path
import shlex
import sys
import subprocess
import json
import contextlib

def parse_args( argv = None ):
    descr = """Use to extract information about C/C++ compiler and linker via
               CMake (with "Unix Makefiles" generator). Will respect and apply
               CMAKE_ARGS environment variable if set (used by conda-forge).

               Run without --findpackageargs and --deptargets results to get the
               basic compilation and link commands and flags.

               To help with escaping troubles, any "@@" in arguments to string
               options will be replaced with a single space.

               Any arguments following a trailing "--" will simply be forwarded
               to the CMake invocation.
    """
    if not argv:
        argv = sys.argv[:]

    parser = argparse.ArgumentParser( prog = os.path.basename(sys.argv[0]),
                                      description=descr )
    parser.add_argument( '-v', '--verbose', action='store_true', default=False )
    parser.add_argument( '-f', '--force', action='store_true', default=False )
    parser.add_argument( '-o', '--output', type=str, default=None,
                         help=("File in which to store results (in JSON format)."
                               " Use 'stdout' (default) and 'stdout_json' to get "
                               "the result pretty printed instead of stored.") )
    parser.add_argument( '-l', '--language', choices=('C','CXX'), default='CXX',
                         help='Language' )
    parser.add_argument( '--findpackage', type=str, nargs='?',const='',
                         help='Arguments for find_package(..) in CMake' )
    parser.add_argument( '--deptargets', type=str, nargs='?', const='',
                         help=('CMake targets/libraries (from the find_package'
                               ' call) which should be investigated for additional'
                               ' compilation and link flags') )

    parser.add_argument( '--respectcmakeargs', action='store_true', default=False,
                         help = ("Respect the CMAKE_ARGS environment variable"
                                 " associated with conda-forge environments." ) )
    parser.add_argument( '--cmakecommand', type=str, default=None,
                         help=("Path to cmake command. If not specified, the"
                               " 'cmake' command in the current path will be used" ) )

    args = argv[1:]
    cmake_args = []
    if '--' in args:
        cmake_args = args[args.index('--')+1:]
        args = args[0:args.index('--')]

    args = parser.parse_args( args )
    for a in ('findpackage','deptargets'):
        v = getattr(args,a)
        if v is not None and not v:
            parser.error(f'Missing value for --{a}')
    if ( args.findpackage is None ) != ( args.deptargets is None ):
        parser.error('Must provide both or neither of the flags'
                     ' --findpackage and --deptargets')
    for a in ('findpackage','deptargets'):
        v = getattr(args,a)
        if v and '@@' in v:
            setattr(args,a,v.replace('@@',' '))
    if not args.output:
        args.output = 'stdout'
    elif args.output not in ('stdout','stdout_json'):
        p = pathlib.Path(args.output)
        p.expanduser()
        p = p.absolute().resolve()
        if p.is_dir():
            parser.error(f'Error: Output file {p} is a directory.')
        if p.exists() and not args.force:
            parser.error(f'Error: Output file {p} already'
                         ' exists (specify --force to overwrite).')
        if not p.parent or not p.parent.is_dir():
            parser.error('Error: Invalid or missing directory'
                         f' for output file {p}.')
        args.output = p

    setattr( args, 'cmakeargs', cmake_args )
    return args

def get_cmake_command( args ):
    if args.cmakecommand:
        ll = [ args.cmakecommand ]
    else:
        import shutil
        ll = [ shutil.which('cmake') ]
    if args.respectcmakeargs:
        #for conda-forge we should always apply CMAKE_ARGS:
        ll += shlex.split(os.environ.get('CMAKE_ARGS',''))
    if args.cmakeargs:
        ll += args.cmakeargs
    #Our procedure only works with the Unix Makefiles generator:
    ll += ['-G','Unix Makefiles']
    return ll

class ParseCmd:
    def __init__( self, cmd, input_file ):
        ll = shlex.split(cmd)
        assert len(ll)>=1
        assert ll.count('-o')==1
        _ = []
        idx_o = ll.index('-o')
        for i,e in enumerate(ll):
            if idx_o <= i <= idx_o+1:
                _.append(e)
                continue
            if e.endswith(input_file) or e.endswith(input_file+'.o'):
                _.append('THE-INPUT-FILE-HERE')
            else:
                _.append(e)
        ll = _

        self.progname = ll[0]
        self.args_preoutput = ll[1:idx_o]
        self.args_postoutput = ll[idx_o+2:]
        self.outputname = ll[idx_o]

    def all_args(self):
        return self.args_preoutput + self.args_postoutput

    def __str__(self):
        return ' '.join(shlex.quote(e) for e in ( [ self.progname ]
                                                  + self.args_preoutput
                                                  + ['-o','THE-OUTPUT-FILE-HERE']
                                                  + self.args_postoutput) )

    def extra_args( self, basecmd ):
        l1 = self.all_args()[:]
        l0 = basecmd.all_args()[:]
        ll = []
        for e in l1:
            if l0 and e==l0[0]:
                l0.pop(0)
                continue
            ll.append(e)
        return ll

def create_cmakeliststxt( args ):
    dummy_usage_statements = ''
    if args.respectcmakeargs:
        #Something in conda-forges CMAKE_ARGS might trigger an unused variable
        #warning, so we make sure we explicitly use them with a dummy statement:
        for e in shlex.split(os.environ.get('CMAKE_ARGS','')):
            if e.startswith('-D'):
                e = e[2:].split('=')[0]
                dummy_usage_statements += '\n# Avoid warning if %s is not used:\n'%e
                dummy_usage_statements += 'if ( DEFINED "%s" )\n'%e
                dummy_usage_statements += '  set( tmp "${%s}" )\n'%e
                dummy_usage_statements += 'endif()\n'
    cmake = """cmake_minimum_required(VERSION 3.24.2...3.27.6)
project( dummy LANGUAGES %s )
%s
set_source_files_properties( "${CMAKE_CURRENT_SOURCE_DIR}/dummy_nodep.input"
                             PROPERTIES LANGUAGE %s)
add_executable(dummy_nodep_app ${CMAKE_CURRENT_SOURCE_DIR}/dummy_nodep.input )
set_target_properties( dummy_nodep_app PROPERTIES LANGUAGE %s )
set_target_properties( dummy_nodep_app PROPERTIES EXPORT_COMPILE_COMMANDS ON )
"""%(args.language,dummy_usage_statements,args.language,args.language)

    if args.findpackage:
        fpargs = args.findpackage
        if 'REQUIRED' not in fpargs:
            fpargs+=' REQUIRED'
        cmake += """
find_package(%s)
set_source_files_properties( "${CMAKE_CURRENT_SOURCE_DIR}/dummy_withdep.input"
                             PROPERTIES LANGUAGE %s)
add_executable(dummy_withdep_app ${CMAKE_CURRENT_SOURCE_DIR}/dummy_withdep.input )
set_target_properties( dummy_withdep_app PROPERTIES LANGUAGE %s )
set_target_properties( dummy_withdep_app PROPERTIES EXPORT_COMPILE_COMMANDS ON )
target_link_libraries( dummy_withdep_app %s )

#foreach( tmp ${FAKE_USAGE_VAR_LIST} )
#  if ( DEFINED "${tmp}" )
#    set( "${tmp}" "${${tmp}}" )
#  endif()
#endforeach()

"""%( fpargs,args.language,args.language,args.deptargets )

    return cmake

def launch_cmake( args, blddir, srcdir ):
    cmd = get_cmake_command( args ) + [ srcdir ]
    cmd_str = ' '.join(shlex.quote(str(c)) for c in cmd)
    if args.verbose:
        print(f"Launching: {cmd_str}")
    def flush():
        ( sys.stdout.flush(), sys.stderr.flush() )
    flush()
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = p.communicate()[0]
        ec = p.returncode
    except ( OSError, subprocess.SubprocessError ):
        raise SystemExit('Error: CMake command failed')
    flush()
    if out and args.verbose:
        sys.stdout.buffer.write(out)
    if ec:
        raise SystemExit('Error: CMake command failed')


@contextlib.contextmanager
def changedir(subdir):
    """Context manager for working in a given subdir and then switching back"""
    the_cwd = os.getcwd()
    os.chdir(subdir)
    try:
        yield
    finally:
        os.chdir(the_cwd)

@contextlib.contextmanager
def work_in_tmpdir():
    """Context manager for working in a temporary directory (automatically
    created+cleaned) and then switching back"""
    import tempfile
    the_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            yield
    finally:
        os.chdir(the_cwd)

def actual_main( args ):
    blddir = ( pathlib.Path('.') / 'bld' ).absolute().resolve()
    srcdir = ( pathlib.Path('.') / 'src' ).absolute().resolve()
    blddir.mkdir()
    srcdir.mkdir()
    dummy_c_or_cpp_main = 'int main(void) { return 0; }\n'
    ( srcdir /'dummy_nodep.input' ).write_text( dummy_c_or_cpp_main )
    if args.findpackage:
        ( srcdir /'dummy_withdep.input' ).write_text( dummy_c_or_cpp_main )

    cmakeliststxt = create_cmakeliststxt( args )
    if args.verbose:
        print('Created CMakeLists.txt >>>\n\n')
        print(cmakeliststxt)
        print('\n\n<<< End of CMakeLists.txt')
    ( srcdir/'CMakeLists.txt' ).write_text(cmakeliststxt)


    with changedir(blddir):
        launch_cmake( args, blddir, srcdir )

    compile_json = json.loads( ( blddir / 'compile_commands.json').read_text() )
    assert len(compile_json)== (2 if args.findpackage else 1)

    def parse_links_txt( name ):
        return ParseCmd( (blddir / 'CMakeFiles'/f'dummy_{name}_app.dir'/'link.txt'
                          ).read_text().strip(),f'dummy_{name}.input' )
    def parse_compile_cmd( name ):
        ll = [ e for e in compile_json
               if ( pathlib.Path(e['file']).name
                    == f'dummy_{name}.input')][0]['command']
        return ParseCmd(ll,f'dummy_{name}.input')

    compile_nodep = parse_compile_cmd('nodep')
    link_nodep = parse_links_txt('nodep')

    out = dict( base = dict( compile
                             = dict( progname = compile_nodep.progname,
                                     args_preoutput = compile_nodep.args_preoutput,
                                     args_postoutput = compile_nodep.args_postoutput ),
                             link
                             = dict( progname = link_nodep.progname,
                                     args_preoutput = link_nodep.args_preoutput,
                                     args_postoutput = link_nodep.args_postoutput ) ) )
    if args.findpackage:
        compile_withdep = parse_compile_cmd('withdep')
        link_withdep = parse_links_txt('withdep')
        out['extra'] = dict( compileflags = compile_withdep.extra_args(compile_nodep),
                             linkflags = link_withdep.extra_args(link_nodep) )

    if args.output=='stdout':
        import pprint
        pprint.pprint(out)
        return
    out_json = json.dumps(out)

    if args.output=='stdout_json':
        print(out_json)
    else:
        args.output.write_text( out_json )

def main( argv = None ):
    args = parse_args( argv = argv )
    with work_in_tmpdir():
        actual_main( args )

if __name__ == '__main__':
    main()
