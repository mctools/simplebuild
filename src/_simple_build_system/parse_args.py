def get_sb_argparse_obj():
    return parse_args(argv=['sb'],
                      sphinx_mode=True)

def parse_args( argv = None,
                return_parser = False,
                sphinx_mode = False ):

    import argparse
    import sys
    import os
    import pathlib

    if argv is None:
        argv = sys.argv[:]
    progname = os.path.basename(argv[0])


    descr="""

Invokes the simplebuild configuration and build system. Usually this means
locating a simplebuild.cfg file in the current (or a parent directory), and
using the corresponding configuration. The default action is to configure and
build those packages, but as described below, certain options might change this
in order to instead display information, launch unit tests, prepare new
projects, etc.


"""

    #Special for --help+--init mode:
    initmode_shorthelp=('Initialise a new simplebuild bundle in the current\n'
                        'directory by creating a simplebuild.cfg file. Use\n'
                        '--init --help for more options.')
    _p = progname
    initmode_longhelp = f"""

New project initialisation mode ("{_p} --init") is used to initialise a new
simplebuild bundle in the current directory by creating a simplebuild.cfg
file. Additional arguments can be used to specify bundles which the new project
should depend on, or they can be a special keyword (DEBUG|COMPACT). In any case,
it might be most convenient to edit the simplebuild.cfg file afterwards to
fine-tune the desired settings.

Examples of {_p} --init usage:

$> {_p} --init core_val

    Set up project which depends on the core_val project.

$> {_p} --init DEBUG

    Set up project with build options for producing debug symbols
    (build.mode='debug').

$> {_p} --init COMPACT

    The resulting simplebuild.cfg file will have all comments and empty lines
    stripped.

$> {_p} --init core_val dgcode COMPACT DEBUG

    Set up project with dependency on core_val and dgcode bundles, with the
    build option for producing debug symbols, and a compact simplebuild.cfg
    file.

    """.strip()+'\n'

    if '--init' in argv and ('-h' in argv or '--help' in argv):
        print(initmode_longhelp)
        raise SystemExit

    parser = argparse.ArgumentParser(
        usage=f'{progname} [-h|--help] [options]',
        description=descr.strip(),
        formatter_class=argparse.RawTextHelpFormatter)

    exclusive = set()

    group_build = parser.add_argument_group(
        'Controlling the build',
        "The build will be carried out and installed in a cache directory "
        "(use -s to\nsee which). The following options affects the build "
        "process.")

    group_qv = group_build.add_mutually_exclusive_group()
    group_qv.add_argument("-v", "--verbose", action="store_true",
                          help="Enable more verbosity.")
    group_qv.add_argument("-q", "--quiet", action="store_true",
                          help='Less verbose. Silence even some warnings.')
    group_build.add_argument(
        "-j", "--jobs",
        type=int, dest="njobs", default=0, metavar="N",
        help="Use up to N parallel processes (default: auto)")
    group_build.add_argument(
        "-e", "--examine",
        action='store_true', dest="examine",
        help="Force (re)examination of environment")
    group_build.add_argument(
        "-i", "--insist",
        action="store_true", dest="insist",
        help="Insist on reconf/rebuild/reinstall from scratch")

    group_query_g = parser.add_argument_group('Query options')
    group_query = group_query_g.add_mutually_exclusive_group()

    group_query.add_argument("--version",
                             action="store_true", dest="show_version",
                             help="Show simplebuild version.")
    exclusive.add(('--version','show_version'))

    group_query.add_argument('-s','--summary',
                             action='store_true', dest='summary',
                             help='Print a summary of the configuration.')
    exclusive.add('summary')

    group_query.add_argument("--pkginfo",
                             action="store", dest="pkginfo", default='',metavar='PKG',
                             help="Print information about package PKG")
    exclusive.add('pkginfo')
    group_query.add_argument("--incinfo",action="store", dest="incinfo",
                             default='',metavar='CFILE',
                             help=( "Show inclusion relationships for CFILE in"
                                    " C++/C\nformat. Specify multiple files with"
                                    " comma-\nseparation and wildcards (\"*\").") )
    exclusive.add('incinfo')
    group_query.add_argument("--pkggraph",
                             action="store_true", dest="pkggraph",
                             help="Create graph of package dependencies")
    exclusive.add('pkggraph')

    group_query.add_argument("--activegraph",
                             action="store_true", dest="pkggraph_activeonly",
                             help="Create graph for enabled packages only")
    exclusive.add(('--activegraph','pkggraph_activeonly'))

    group_query.add_argument("--grep",action="store", dest="grep",
                             default='',metavar='PATTERN',
                             help="Grep files in packages for PATTERN")
    exclusive.add('grep')
    group_query.add_argument("--grepc",action="store", dest="grepc",
                             default='',metavar='PATTERN',
                             help="Like --grep but show only count per package")
    exclusive.add('grepc')
    group_query.add_argument("--find",action="store", dest="find",
                             default=None, metavar='PATTERN',
                             help=("Search for file and path names"
                                   " matching PATTERN"))
    exclusive.add('find')

    group_init = parser.add_argument_group('New project initialisation options')
    group_init.add_argument('--init', action='store_true', dest='init',
                            help=(initmode_longhelp
                                  if sphinx_mode else initmode_shorthelp ))
    exclusive.add('init')

    group_test = parser.add_argument_group('Unit testing options')

    group_test.add_argument("-t", "--tests",
                           action="store_true", dest="runtests",
                           help="Run unit tests after the build")
    exclusive.add(('--tests','runtests'))
    group_test.add_argument("--testexcerpts", type=int, dest="nexcerpts",
                            default=0,metavar="N",
                            help=("Print N first+last lines of failed test log"
                                  " files."))
    group_test.add_argument("--testfilter", type=str, dest="testfilter",
                            default='', metavar="PATTERN",
                            help=('Only run tests with names matching at least '
                                  'one\nof the provided patterns (use wildcards,'
                                  ' comma\nseparation, and "!" prefix to'
                                  ' negate).'),)

    group_other = parser.add_argument_group('Other options')


    group_other.add_argument("-c", "--clean",
                             action='store_true', dest="clean",
                             help=("Completely remove cache directories and"
                                   " exit."))
    exclusive.add('clean')

    group_other.add_argument("--replace", action="store", dest="replace",
                             default=None, metavar='PATTERN',
                             help=("Global search and replace in packages via"
                                   " pattern\nlike '/OLDCONT/NEWCONT/' (use "
                                   "with care!)"))
    exclusive.add('replace')

    group_other.add_argument("--removelock",
                           action='store_true', dest="removelock",
                           help="Force removal of lockfile")

    group_other.add_argument("--env-setup",
                             action="store_true", dest="env_setup",
                             help=("Emit shell code needed to modify"
                                   " environment\nvariables to use"
                                   " build packages, then exit."))
    exclusive.add(('--env-setup','env_setup'))

    a=group_other.add_argument("--env-unsetup",
                             action="store_true", dest="env_unsetup",
                             help=("Emit shell code undoing the effect of"
                                   " any\nprevious --env-setup usage, then exit."))
    exclusive.add(('--env-unsetup','env_unsetup'))

    if sphinx_mode:
        return parser
    args, args_unused = parser.parse_known_args(argv[1:])
    bad_unused=list(a for a in args_unused if a.startswith('-'))
    if bad_unused:
        parser.error('unknown argument: %s'%bad_unused[0])

    present_exclusive = set()
    for a in exclusive:
        if isinstance(a,str):
            flag,attr='--%s'%a,a
        else:
            flag,attr=a
        if bool(getattr(args,attr)):
            present_exclusive.add(flag)
    if len(present_exclusive)>1:
        f1=list(present_exclusive)[0]
        f2=list(present_exclusive)[1]
        parser.error(f'arguments {f1} and {f2} are mutually exclusive')

    if args.grepc:
        args.grep=args.grepc
        args.grepc=bool(args.grepc)

    if args.pkggraph_activeonly:
        args.pkggraph=True

    #Some query option require that we always load all package meta
    #data. Additionally, some have "pathzoom", and use the unused positional
    #arguments as path filters:
    query_mode_withpathzoom_n = sum(int(bool(a)) for a in [args.grep,
                                                           args.replace,
                                                           args.find])
    query_mode_n = query_mode_withpathzoom_n + sum(int(bool(a))
                                                   for a in
                                                   [args.pkggraph,
                                                    args.pkginfo,args.
                                                    incinfo,args.summary])
    if int(args.clean)+ query_mode_n > 1:
        parser.error("Conflicting options (+internal inconsistency:"
                     " this conflict should have been caught earlier)")
    args.query_mode = query_mode_n > 0

    args.querypaths=[]

    if query_mode_withpathzoom_n > 0:
        for a in args_unused:
            qp = pathlib.Path(a).expanduser()
            if not qp.exists():
                parser.error(f'Path not found: {qp}')
            qp = qp.absolute().resolve()
            args.querypaths.append(qp)
        args_unused=[]

    if args.init:
        from .singlecfg import is_valid_bundle_name
        args.init = []
        for a in args_unused:
            if not is_valid_bundle_name(a):
                parser.error(f'Invalid name for dependency bundle: {a}')
            args.init.append( a )
        args_unused = []
    else:
        args.init = None

    if args_unused:
        parser.error("Unrecognised arguments: %s"%' '.join(args_unused))

    if return_parser:
        return parser, args
    else:
        return args
