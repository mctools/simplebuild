#Build script which is intended to make the following steps smooth, painless and efficient for users:
#
#  1) Detect environment with cmake
#  2) Configuration step
#  3) Build step
#  4) Install step
#  5) Test launch.
#
# Most importantly, it is intended that minimal cpu time is used to needless redo work in steps 1-4
# above when user changes code or configuration.

import sys
import os
import glob
import shlex
import pathlib

def simplebuild_main( argv = None, prevent_env_setup_msg = False ):
    if argv  is None:
        argv = sys.argv[:]

    #Always inspect cfg and set up appropriate warnings/error printouts:
    from . import error
    from . import conf

    error.fmt_simplebuild_warnings()

    progname=os.path.basename(argv[0])
    prefix = conf.print_prefix
    print = conf.print

    from optparse import OptionParser,OptionGroup#FIXME: deprecated, use argparse instead!

    def isfile(s):
        return os.path.exists(s) and not os.path.isdir(s)

    #########################
    ### Parse arguments  ####
    #########################

    legacy_mode = False

    def get_simplebuild_pkg_dirs():
        from . import dirs
        return [dirs.projdir, *dirs.extrapkgpath]

    if legacy_mode:
        from . import dirs # noqa: F811
        rel_blddir=os.path.relpath(dirs.blddir)
        rel_instdir=os.path.relpath(dirs.installdir)


    if legacy_mode:
        from . import envcfg
        proj_pkg_selection_enabled = envcfg.var.enable_projects_pkg_selection_flag
    else:
        proj_pkg_selection_enabled = False
    def parse_args():

        #Prepare parser:
        parser = OptionParser(usage='%prog [options]')

        if legacy_mode:
            group_build = OptionGroup(parser, "Controlling the build","The build will be carried out"
                                      " in the %s/ directory and after a successful build it"
                                      " will install the results in %s/. In addition to"
                                      " configuration variables, the follow options can be used to fine-tune"
                                      " the build process."%(rel_blddir,rel_instdir))
        else:
            group_build = OptionGroup(parser, "Controlling the build","The build will be carried out"
                                      " and installed in a cache directory (use --info to see which). In addition to"
                                      " configuration variables, the follow options can be used to fine-tune"
                                      " the build process.")

        group_build.add_option("-j", "--jobs",
                               type="int", dest="njobs", default=0,
                               help="Use up to N parallel processes",metavar="N")
        group_build.add_option("-v", "--verbose",
                               action='store_true', dest="verbose", default=False,
                               help="Enable more verbosity")
        group_build.add_option("-q", "--quiet",
                               action='store_true', dest="quiet", default=False,
                               help="Less verbose. Silence even some warnings")
        group_build.add_option("-e", "--examine",
                               action='store_true', dest="examine", default=False,
                               help="Force (re)examination of environment")
        group_build.add_option("-i", "--insist",
                               action="store_true", dest="insist", default=False,
                               help="Insist on reconf/rebuild/reinstall from scratch")#nb: does not forget CMake args!
        parser.add_option_group(group_build)

        group_cfgvars = OptionGroup(parser, "Setting configuration variables",
                                    "You can set variables to be used during the configuration stage. Once"
                                    " set, the variables will be remembered and do not need to be specified"
                                    " upon next invocation of %s. Use the -s switch for more info."%progname)
        group_cfgvars.add_option("-s", "--show",
                                 action='store_true', dest="show", default=False,
                                 help="Show stored configuration variables and exit")
        group_cfgvars.add_option("-f", "--forget",
                                 action='store_true', dest="forget", default=False,
                                 help="Forget stored configuration variables and exit")
        group_cfgvars.add_option("-r", "--release",
                                 action='store_true', dest="release", default=False,
                                 help="Shortcut for CMAKE_BUILD_TYPE=RELEASE")
        group_cfgvars.add_option("-d", "--debug",
                                 action='store_true', dest="debug", default=False,
                                 help="Shortcut for CMAKE_BUILD_TYPE=DEBUG")
        parser.add_option_group(group_cfgvars)

        if legacy_mode:

            group_pkgselect = OptionGroup(parser, "Selecting what packages to enable",
                                          "The flags below provide a convenient alternative to"
                                          " direct modification of the configuration variable named \"ONLY\". Default is to enable all packages.")
            group_pkgselect.add_option("-a","--all",action='store_true', default=False,dest='enableall',
                                     help="Enable *all* packages.")

            if proj_pkg_selection_enabled:
              group_pkgselect.add_option("-p","--project",
                                     action='store', dest="project", default='',metavar='PROJ',
                                     help=('Enable packages in selected projects under $DGCODE_PROJECTS_DIR'
                                           +' (defined by the name of their top-level directory under $DGCODE_PROJECTS_DIR).'))

            parser.add_option_group(group_pkgselect)

        group_query = OptionGroup(parser, "Query options")

        #FIXME: Should be something simple like -s (after we retire the current way of setting cmake args
        if not legacy_mode:
            group_query.add_option('--cfginfo',
                                   action='store_true', dest='cfginfo', default=False,
                                   help='Print overall configuration information (based on the simplebuild.cfg file) and exit.')


        group_query.add_option("--pkginfo",
                               action="store", dest="pkginfo", default='',metavar='PKG',
                               help="Print information about package PKG")
        group_query.add_option("--incinfo",
                               action="store", dest="incinfo", default='',metavar='CFILE',
                               help="Show inclusion relationships for the chosen CFILE. CFILE must be a C++ or C file in the package search path. Optionally multiple files can be specified using comma-separation and wildcards (\"*\').")
        group_query.add_option("--pkggraph",
                               action="store_true", dest="pkggraph", default=False,
                               help="Create graph of package dependencies")
        group_query.add_option("--activegraph",
                               action="store_true", dest="pkggraph_activeonly", default=False,
                               help="Create graph for enabled packages only")
        group_query.add_option("--grep",
                               action="store", dest="grep", default='',metavar='PATTERN',
                               help="Grep files in packages for PATTERN")
        group_query.add_option("--grepc",
                               action="store", dest="grepc", default='',metavar='PATTERN',
                               help="Like --grep but show only count per package")
        group_query.add_option("--find",
                               action="store", dest="find", default=None, metavar='PATTERN',
                               help="Search for file and path names matching PATTERN")
        parser.add_option_group(group_query)

        group_other = OptionGroup(parser, "Other options")
        group_other.add_option("-t", "--tests",
                               action="store_true", dest="runtests", default=False,
                               help="Run tests after the build")
        group_other.add_option("--testexcerpts",
                               type="int", dest="nexcerpts", default=0,
                               help="Show N first and last lines of each log file in failed tests",metavar="N")
        group_other.add_option("--testfilter",
                               type="str", dest="testfilter", default='',
                               help="Only run tests with names matching provided patterns (passed on to 'dgtests --filter', c.f. 'dgtests --help' for details)",metavar="PATTERN")
        if legacy_mode:
            group_other.add_option("-c", "--clean",
                                   action='store_true', dest="clean", default=False,
                                   help="Remove %s and %s directories and exit"%(rel_blddir,rel_instdir))
        else:
            group_other.add_option("-c", "--clean",
                                   action='store_true', dest="clean", default=False,
                                   help="Completely remove cache directories and exit.")
        group_other.add_option("--replace",
                               action="store", dest="replace", default=None, metavar='PATTERN',
                               help="Global search and replace in packages via pattern like '/OLDCONT/NEWCONT/' (use with care!)")
        group_other.add_option("--removelock",
                               action='store_true', dest="removelock", default=False,
                               help="Force removal of lockfile")

        group_other.add_option("--env-setup",
                               action="store_true", dest="env_setup", default=False,
                               help="Emit shell code needed to modify environment variables to use build packages, then exit.")
        group_other.add_option("--env-unsetup",
                               action="store_true", dest="env_unsetup", default=False,
                               help="Emit shell code undoing the effect of any previous --env-setup usage, then exit.")

        parser.add_option_group(group_other)

        #Actually parse arguments, taking care that the ones of the form VAR=value
        #must be interpreted as user configuration choices, most passed to cmake.
        new_cfgvars={}
        args_unused=[]
        (opt, args) = parser.parse_args(argv[1:])
        for a in args:
            t=a.split('=',1)
            if len(t)==2 and t[0] and ' ' not in t[0]:
                if t[0] in new_cfgvars:
                    parser.error('Configuration variable %s supplied multiple times'%t[0])
                new_cfgvars[t[0]]=t[1]
            else:
                args_unused+=[a]
        del args

        opt._querypaths=[]
        if opt.grepc:
            if opt.grep:
                parser.error("Don't supply both --grep and --grepc")
            opt.grep=opt.grepc
            opt.grepc=bool(opt.grepc)

        if legacy_mode:
            opt.cfginfo = False

        if new_cfgvars and (opt.forget or opt.clean or opt.pkginfo or opt.grep or opt.incinfo or opt.cfginfo):
            parser.error("Don't supply <var>=<val> arguments together with --cfginfo, --clean, --forget, --grep, --incinfo, --pkginfo flags")

        if opt.pkggraph_activeonly:
            opt.pkggraph=True

        #rel/debug flags:
        if opt.release and opt.debug:
            parser.error('Do not supply both --debug and --release flags')
        if (opt.release or opt.debug) and 'CMAKE_BUILD_TYPE' in new_cfgvars:
            parser.error('Do not supply --debug or --release flags while setting CMAKE_BUILD_TYPE directly')
        if opt.release:
            new_cfgvars['CMAKE_BUILD_TYPE']='RELEASE'
        if opt.debug:
            new_cfgvars['CMAKE_BUILD_TYPE']='DEBUG'

        if legacy_mode and proj_pkg_selection_enabled:
          if opt.project and opt.enableall:
            parser.error('Do not specify both --all and --project')

          if opt.project:
              #TODO: This is rather specific to our way of structuring directories...
              if 'ONLY' in new_cfgvars:
                  parser.error('Do not set ONLY=... variable when supplying --project flag')
              #if 'NOT' in new_cfgvars:
              #    parser.error('Do not set NOT=... variable when supplying --project flag')
              projs = set(e.lower() for e in opt.project.split(','))
              extra='Framework::*,'
              from . import dirs
              if dirs.extrapkgpath:
                  extra+='Extra::*,'
              if not projs:
                  extra=extra[:-1]#remove comma
              new_cfgvars['ONLY']='%s%s'%(extra,','.join('Projects::%s*'%p for p in projs))
              if 'NOT' not in new_cfgvars:
                  new_cfgvars['NOT']=''

        #if opt.pkgs and opt.enableall:
            #parser.error('Do not specify both --all and --project')

    #    if opt.pkgs:
    #        if 'ONLY' in new_cfgvars:
    #            parser.error('Do not set ONLY=... variable when supplying --pkg flag')
    #        if 'NOT' in new_cfgvars:
    #            parser.error('Do not set NOT=... variable when supplying --pkg flag')
    ##    if opt.pkgs:
    ##        pkgs = set(e.lower() for e in opt.pkg.split(','))
    ##        _only=new_cfgvars.get('ONLY','')
    ##        new_cfgvars['ONLY']='%s%s'%(extra,','.join('Projects/%s*'%p for p in projs))
    ##        new_cfgvars['NOT']=''
    ##     .... todo...

        if legacy_mode and opt.enableall:
            if 'ONLY' in new_cfgvars:
                parser.error('Do not set ONLY=... variable when supplying --all flag')
            #if 'NOT' in new_cfgvars:
            #    parser.error('Do not set NOT=... variable when supplying --all flag')
            if 'NOT' not in new_cfgvars:
                new_cfgvars['NOT']=''
            new_cfgvars['ONLY']='*'#this is how we make sure --all is remembered

        query_mode_withpathzoom_n = sum(int(bool(a)) for a in [opt.grep,opt.replace,opt.find])
        query_mode_n = query_mode_withpathzoom_n + sum(int(bool(a)) for a in [opt.pkggraph,opt.pkginfo,opt.incinfo,opt.cfginfo])
        if int(opt.forget)+int(opt.show)+int(opt.clean)+ query_mode_n > 1:
            parser.error("More than one of --clean, --forget, --show, --pkggraph, --pkginfo, --grep, --grepc, --replace, --find, --cfginfo, --incinfo specified at the same time")
        opt.query_mode = query_mode_n > 0
        if query_mode_withpathzoom_n > 0:
            for a in args_unused:
                qp=os.path.abspath(os.path.realpath(a))
                simplebuild_pkg_dirs = get_simplebuild_pkg_dirs()
                if not any([qp.startswith(str(d)) for d in simplebuild_pkg_dirs]):
                    parser.error("grep/find/replace/... can only work on directories below %s"%simplebuild_pkg_dirs) #TODO ' '.join(simplebuild_pkg_dirs) might look nicer
                gps=[d for d in glob.glob(qp) if os.path.isdir(d)]
                if not gps:
                    parser.error("no directory matches for '%s'"%a)
                for d in sorted(gps):
                  opt._querypaths+=['%s/'%os.path.relpath(d,str(codedir)) for codedir in simplebuild_pkg_dirs if d.startswith(str(codedir))]
            args_unused=[]

        if args_unused:
            parser.error("Unrecognised arguments: %s"%' '.join(args_unused))

        if opt.verbose and opt.quiet:
            parser.error("Do not supply both --quiet and --verbose flags")


        return parser,opt,new_cfgvars

    parser,opt,new_cfgvars=parse_args()
    if opt.quiet:
        conf.make_quiet()

    if opt.env_setup:
        from .envsetup import emit_envsetup
        emit_envsetup()
        raise SystemExit

    if opt.env_unsetup:
        from .envsetup import emit_env_unsetup
        emit_env_unsetup()
        raise SystemExit

    if opt.cfginfo:
        assert not legacy_mode
        print("FIXME: cfginfo mode is not yet implemented!")
        raise SystemExit

    #setup lockfile:
    from . import dirs
    from . import conf
    from . import envcfg
    from . import utils
    if opt.removelock and dirs.lockfile.exists():
        os.remove(dirs.lockfile)

    if dirs.lockfile.exists():
        error.error('ERROR: Presence of lock file indicates competing invocation of '
                    '%s. Force removal with %s --removelock if you are sure this is incorrect.'%(progname,progname))
    dirs.create_bld_dir()

    utils.touch(dirs.lockfile)

    assert dirs.lockfile.exists()
    def unlock():
        from os import remove
        from .dirs import lockfile
        if lockfile.exists():
            remove(lockfile)
    import atexit
    atexit.register(unlock)

    if opt.clean:
        if dirs.blddir.is_dir() or dirs.installdir.is_dir():
            if not opt.quiet:
                print("Removing temporary cache directories and forgetting stored CMake args. Exiting.")
            conf.safe_remove_install_and_build_dir()
        else:
            if not opt.quiet:
                print("Nothing to clean. Exiting.")
        sys.exit(0)
    try:
        old_cfgvars = utils.pkl_load(dirs.varcache)
    except IOError:
        old_cfgvars = {}

    if opt.forget:
        if old_cfgvars:
            os.remove(dirs.varcache)
            if not opt.quiet:
                print("Cleared %i configuration variable%s."%(len(old_cfgvars),'' if len(old_cfgvars)==1 else 's'))
        else:
            if not opt.quiet:
                print("No configuration variables set, nothing to clear.")
        sys.exit(0)

    #combine old and new config vars:
    cfgvars=dict((k,v) for k,v in new_cfgvars.items() if v)
    for k,v in old_cfgvars.items():
        if k not in new_cfgvars:
            cfgvars[k]=v

    #Make sure that if nothing is specified, we compile ALL packages,
    #or just Framework packages if project package selection is enabled (+ all extrapkgpath packages, if the path is set):
    if legacy_mode:
        pkg_selection_default = "*" if not proj_pkg_selection_enabled else ("Framework::*,Extra::*" if dirs.extrapkgpath else "Framework::*")
        if 'NOT' not in cfgvars and 'ONLY' not in cfgvars: #and not opt.pkgs
            cfgvars['ONLY'] = pkg_selection_default

    #Old check, we try to allow both variables now:
    #if 'ONLY' in cfgvars and 'NOT' in cfgvars:
    #    parser.error('Can not set both ONLY and NOT variables simultaneously. Unset at least one by ONLY="" or NOT=""')

    #Detect changes to system cmake or python files and set opt.examine or opt.insist as appropriate.
    from . import mtime
    systs = (mtime.mtime_cmake(),mtime.mtime_pymods())
    try:
        oldsysts = utils.pkl_load(dirs.systimestamp_cache)
    except IOError:
        opt.insist=True
        oldsysts = (None,None)

    if envcfg.var.allow_sys_dev:
        #prevent changes in system from triggering rebuilds (for careful system
        #development use):
        systs = oldsysts

    if not opt.insist and oldsysts!=systs:
        if oldsysts[0]!=systs[0]:
            opt.examine = True
        if oldsysts[1]!=systs[1]:
            opt.insist = True

    if dirs.envcache.exists():
        envdict=utils.pkl_load(dirs.envcache)
        #insist rebuilding from scratch if install dir was changed since the build dir was last used
        _autoreconf_cache_dirs = envdict['_autoreconf_environment'][0]
        assert _autoreconf_cache_dirs[0][0]=='install_dir'
        assert _autoreconf_cache_dirs[1][0]=='build_dir'
        _autoreconf_inst_dir = _autoreconf_cache_dirs[0][1]
        _autoreconf_bld_dir = _autoreconf_cache_dirs[1][1]
        if ( _autoreconf_inst_dir != str(conf.install_dir())
             or _autoreconf_bld_dir != str(conf.build_dir()) ):
            opt.insist = True

    if opt.insist:
        conf.safe_remove_install_and_build_dir()
        dirs.create_bld_dir()

    utils.pkl_dump(cfgvars,dirs.varcache)
    utils.pkl_dump(systs,dirs.systimestamp_cache)

    if opt.show:
        if cfgvars:
            if not opt.quiet:
                print('Currently the following configuration variables are set:')
            if not opt.quiet:
                print()
            #print the values even when quiet:
            for k,v in sorted(cfgvars.items()):
                print('    %s=%s'%(k,shlex.quote(v)))
        else:
            if not opt.quiet:
                print('Currently no configuration variables are set.')
        if not opt.quiet:
            print()
            print('To modify this you can (note this is mostly for expert users!):')
            print()
            print('  - set variable by supplying VAR=VAL arguments to %s'%progname)
            print('  - unset a variable by setting it to nothing (VAR=)')
            print('  - unset all variables by running %s with --forget (but note that'%progname)
            print('    the ONLY variable is special and defaults to "%s")'%(pkg_selection_default))
            print()
            print('These are the variables with special support in %s'%progname)
            print()
            print('  - SBLD_EXTRA_CFLAGS  : Extra compilation flags to be passed to the compiler')
            print('                         Example: SBLD_EXTRA_CFLAGS=-Wshadow')
            print('  - SBLD_EXTRA_LDFLAGS : Extra link flags to be passed to the linker')
            print('  - SBLD_RELAX         : Set to 1 to temporarily ignore compiler warnings')
            print('  - ONLY               : Enable only certain packages.')
            print('                         Example: ONLY="Framework::*,BasicExamples"')
            print('  - NOT                : Disable certain packages.')
            print('  - Geant4=0, ROOT=0, etc.. : Force a given external dependency to be')
            print('                              considered as absent, even if present.')
        sys.exit(0)

    def create_filter(pattern):
        #fixme soon obsolete
        #Patterns separated with ; or ,.
        #
        #A '/' char indicates a pattern to be tested versus the path to the package,
        #otherwise it will be a test just against the package name.
        #
        #matching is done case-insensitively via the fnmatch module

        aliases = dirs.pkgdir_aliases
        def expand_alias(part):
          if '::' not in part:
            return [part]
          pkgdirAlias = part.split('::')[0].lower()
          subdirPattern = part.split('::')[1].lower()
          if pkgdirAlias in aliases:
            pkgdir = aliases[pkgdirAlias]
            if isinstance(pkgdir,list):
              return [os.path.join(d, subdirPattern) for d in pkgdir]
            else:
              return [os.path.join(pkgdir,subdirPattern)]
          else:
            print("Error: Can't find directory alias for %s in %s"%(part.split('::')[0],part))
            sys.exit(1)

        # Separate patterns, and expand directory aliases
        pattern_parts = [item for p in pattern.replace(';',',').split(',') if p for item in expand_alias(p)]

        import fnmatch
        import re
        namepatterns = []
        dirpatterns = []
        for p in pattern_parts:
          if '/' not in p:
            namepatterns.append(re.compile(fnmatch.translate(p.lower())).match)
          elif p.startswith('/'):
            dirpatterns.append(re.compile(fnmatch.translate(p.lower())).match)
          else:
            # create pattern for ALL paths in the pkg search path
            dirpatterns.extend([re.compile(fnmatch.translate( ('%s/%s'%(d,p)).lower() )).match for d in dirs.pkgsearchpath])

        def the_filter(pkgname,absdir):
            for p in namepatterns:
                if p(pkgname.lower()):
                    return True
            for d in dirpatterns:
                if d(absdir.lower()):
                    return True
            return False

        return the_filter

    if legacy_mode:
        select_filter=create_filter(cfgvars['ONLY']) if 'ONLY' in cfgvars else None
        exclude_filter=create_filter(cfgvars['NOT']) if 'NOT' in cfgvars else None
        cmakeargs=[shlex.quote('%s=%s'%(k,v)) for k,v in cfgvars.items() if k not in set(['ONLY','NOT'])]
        cmakeargs.sort()
    else:
        #fixme: cleanup variable usage after migration!
        select_filter = envcfg.var.pkg_filter
        assert select_filter is not None
        exclude_filter = 'NOTLEGACYMODE'
        if 'ONLY' in cfgvars or 'NOT' in cfgvars:
            error.error('Do not use old-school -p/-a/ONLY=/NOT= mode for filtering packages.'
                        ' Instead add a [build] pkg_filter = ["filter",...] entry in your main simplebuild.cfg.')
        cmakeargs = []#fixme



    autodisable = True

    from . import backend

    err_txt,unclean_exception = None,None
    error.default_error_type = error.Error
    try:
        pkgloader = backend.perform_configuration(cmakeargs=cmakeargs,
                                                  select_filter=select_filter,
                                                  exclude_filter=exclude_filter,
                                                  autodisable = autodisable,
                                                  force_reconf=opt.examine,
                                                  load_all_pkgs = opt.query_mode,
                                                  prefix=prefix,
                                                  quiet=opt.quiet,
                                                  verbose=opt.verbose)
    except KeyboardInterrupt:
        err_txt = "Halted by user interrupt (CTRL-C)"
    except error.CleanExit as ce:
        #errors already handled, exit directly:
        sys.exit(ce._the_ec)
    except Exception as e:
        err_txt=str(e)
        if not err_txt:
            err_txt='<unknown error>'
        if not isinstance(e,error.Error):
            unclean_exception = e
    except SystemExit as e:
        if str(e)!="knownhandledexception":
            err_txt = "Halted by unexpected call to system exit!"
            unclean_exception = e

    error.default_error_type = SystemExit

    if err_txt:
        pr="\n\nERROR during configuration:\n\n  %s\n\nAborting."%(err_txt.replace('\n','\n  '))
        print(pr.replace('\n','\n%s'%prefix))
        #make all packages need reconfig upon next run:
        from . import db
        db.db['pkg2timestamp']={}
        db.save_to_file()
        #exit (with ugly traceback if unknown type of exception):
        if unclean_exception:
            error.print_traceback(unclean_exception,prefix)
        sys.exit(1)

    assert dirs.makefiledir.is_dir()

    def query_pkgs():
        l=[]
        for p in sorted(pkgloader.pkgs):
            if not opt._querypaths:
                l+=[p]
            else:
                for qp in opt._querypaths:
                    if (p.reldirname+'/').startswith(qp):
                        l+=[p]
                        break
        return l

    if opt.grep:
        qp=query_pkgs()
        print("Grepping %i packages for pattern %s\n"%(len(qp),opt.grep))
        n=0
        from . import grep
        for pkg in qp:
            n+=grep.grep(pkg,opt.grep,countonly=opt.grepc)
        print("\nFound %i matches"%n)
        sys.exit(0)

    if opt.replace:
        qp=query_pkgs()
        p=opt.replace
        from . import replace
        search_pat,replace_pat = replace.decode_pattern(opt.replace)
        if not search_pat:
            parser.error("Bad syntax in replacement pattern: %s"%p)
        print("\nReplacing all \"%s\" with \"%s\""%(search_pat,replace_pat))
        n = 0
        for pkg in qp:
            n+=replace.replace(pkg,search_pat,replace_pat)
        print("\nPerformed %i replacements"%n)
        sys.exit(0)

    if opt.find:
        qp=query_pkgs()
        p=opt.find
        from . import find#fnmatch!!
        print("\nFinding all files and paths matching \"%s\"\n"%(p))
        n = 0
        for pkg in qp:
            n+=find.find(pkg,p)
        print("\nFound %i matches"%n)
        sys.exit(0)

    if opt.incinfo:
        def _val_incinfofn(fn):
            if '*' in fn:
                #try to expand wildcards:
                fff = sorted(glob.glob(fn))
                if fff:
                    return sum((_val_incinfofn(ff) for ff in fff),[])
            if not os.path.exists(fn):
                #Could be of form "pkgname/subdir/file. If so, expand pkgname part
                #to full path to package:
                i=fn.split(os.path.sep)
                pkg=pkgloader.name2pkg.get(i[0],None) if len(i)==3 else None
                if pkg:
                    return _val_incinfofn(dirs.pkg_dir(pkg,i[1],i[2]))
                else:
                    parser.error("File not found: %s"%fn)
            if os.path.isdir(fn):
                parser.error("Not a file: %s"%fn)
            fn=os.path.abspath(os.path.realpath(fn))
            p = pathlib.Path(fn).absolute().resolve()
            simplebuild_pkg_dirs = get_simplebuild_pkg_dirs()
            if not any( utils.path_is_relative_to(p,d) for d in simplebuild_pkg_dirs):
                #TODO: This currently fails for dynamic packages!
                parser.error(f"File {p} must be located under one of the following directories:\n%s"%('\n '.join(str(e) for e in simplebuild_pkg_dirs)))
            return [fn]#expands to a single file
        from . import incinfo
        fnsraw = opt.incinfo.split(',') if ',' in opt.incinfo else [opt.incinfo]
        fns = sum((_val_incinfofn(fnraw) for fnraw in fnsraw),[])
        #remove duplicates (relies on seen.add returning None)
        seen=set()
        fns = [fn for fn in fns if not (fn in seen or seen.add(fn))]
        #Dispatch to backend:
        if len(fns)==1:
            incinfo.provide_info(pkgloader,fns[0])
        else:
            incinfo.provide_info_multifiles(pkgloader,fns)
        sys.exit(0)

    if opt.pkginfo:
        pkg=pkgloader.name2pkg.get(opt.pkginfo,None)
        if not pkg:
            utils.err('Unknown package "%s"'%opt.pkginfo)
        else:
            pkg.dumpinfo(pkgloader.autodeps,prefix)
            sys.exit(0)

    if opt.pkggraph:
        dotfile=dirs.blddir / 'pkggraph.dot'
        from . import dotgen
        dotgen.dotgen(pkgloader,dotfile,enabled_only=opt.pkggraph_activeonly)
        if not opt.quiet:
            print('%sPackage dependencies in graphviz DOT format has been generated in %s'%(prefix,dotfile))
        ec=utils.system('dot -V > /dev/null 2>&1')
        if ec:
            if not opt.quiet:
                print('Warning: command "dot" not found or ran into problems.')
                print('Please install graphviz to enable graphical dependency displays')
            sys.exit(1)
        ec=utils.system('unflatten -l3 -c7 %s|dot -Tpng -o%s/pkggraph.png'%(dotfile,dirs.blddir))
        if ec or not isfile('%s/pkggraph.png'%dirs.blddir):
            if not opt.quiet:
                print('Error: Problems with dot command while transforming pkggraph.dot to pkggraph.png')
            sys.exit(1)
        else:
            if not opt.quiet:
                print('Package dependencies in PNG format has been generated in %s/pkggraph.png'%dirs.blddir)
        sys.exit(0)


    if not opt.njobs:
        from . import cpudetect
        opt.njobs=cpudetect.auto_njobs(prefix)

    #VERBOSE:
    # -1: always quiet
    #  0: only warnings
    #  1: extra verbose printouts
    if opt.verbose:
        extramakeopts=' VERBOSE=1'
    elif opt.quiet:
        extramakeopts=' VERBOSE=-1'
    else:
        extramakeopts=''
    if not opt.quiet:
        print("Configuration completed => Launching build with %i parallel processes"%opt.njobs)

    assert dirs.makefiledir.is_dir()
    ec=utils.system("cd %s && make --warn-undefined-variables -f Makefile -j%i%s"%(dirs.makefiledir,opt.njobs,extramakeopts))
    if ec!=0:
        if not opt.quiet:
            print("ERROR: Build problems encountered")
        sys.exit(1 if ec > 128 else ec)

    if not opt.quiet:
        print()
        print('%sSuccessfully built and installed all enabled packages!'%prefix)
        print()
        print('%sSummary:'%prefix)
        def fixpath( p ):
            if envcfg.var.conda_prefix:
                pabs = p.absolute().resolve()
                cp = pathlib.Path(envcfg.var.conda_prefix).absolute().resolve()
                if cp.is_dir() and utils.path_is_relative_to( pabs, cp ):
                    return os.path.join('${CONDA_PREFIX}',str(pabs.relative_to(cp)))
            return str(p)
        print('  Projects directory               : %s'%fixpath(dirs.projdir))
        print('  Installation directory           : %s'%fixpath(dirs.installdir))
        print('  Build directory                  : %s'%fixpath(dirs.blddir))

        from . import col
        col_ok = col.ok
        col_bad = col.bad
        col_end = col.end
        #FIXME: Use formatlist module!
        def formatlist(lin,col):
            l=lin[:]
            colbegin = col if col else ''
            colend = col_end if col else ''
            if not l or l==['']:
                return '<none>'
            first=True
            out=''
            while l:
                s=''
                while l and len(s)<40:
                    if s:
                        s += ' '
                    s += l.pop(0)
                if first:
                    out+='%s%s%s'%(colbegin,s,colend)
                    first=False
                else:
                    out += '\n%s                                     %s%s%s'%(prefix,colbegin,s,colend)
            return out
            #return ' '.join(l)

        pkg_src_info = []
        for basedir in dirs.pkgsearchpath:
            pkg_nr = len([p.name for p in pkgloader.pkgs if p.dirname.startswith(str(basedir))])
            pkg_enabled = len([p.name for p in pkgloader.pkgs if p.enabled and p.dirname.startswith(str(basedir))])
            pkg_src_info.append([basedir, pkg_enabled, (pkg_nr-pkg_enabled) ])

        def pkg_info_str(info):
            p=fixpath(info[0])
            if info[1]+info[2]==0:
                descr='no pkgs'
            else:
                nbuilt = '%s%d%s'%(col_ok,info[1],col_end) if info[1]!=0 else '0'
                nskipped = '%s%d%s'%(col_bad,info[2],col_end) if info[2]!=0 else '0'
                descr='%s built, %s skipped'%(nbuilt, nskipped)
            return "%s (%s)"%(p, descr)

        print('  Package search path              : %s'%formatlist([pkg_info_str(info) for info in pkg_src_info],None))

        nmax = 20
        pkg_enabled = sorted([p.name for p in pkgloader.pkgs if p.enabled])
        n_enabled = len(pkg_enabled)
        lm2='(%i more,'
        limittxt=['...',lm2,'supply','--verbose','to','see','all)']
        if not opt.verbose and n_enabled>nmax:
            limittxt[1] = lm2%(n_enabled-nmax)
            pkg_enabled = pkg_enabled[0:nmax]+limittxt
        pkg_disabled = sorted([p.name for p in pkgloader.pkgs if not p.enabled])
        n_disabled = len(pkg_disabled)
        if not opt.verbose and n_disabled>nmax:
            limittxt[1] = lm2%(n_disabled-nmax)
            pkg_disabled = pkg_disabled[0:nmax]+limittxt
        from . import env
        extdeps_avail = sorted(k for (k,v) in env.env['extdeps'].items() if v['present'])
        extdeps_missing = sorted(k for (k,v) in env.env['extdeps'].items() if not v['present'])

        #Compilers (Fortran is considered optional), CMake, and required externals deps like Python and pybind11:
        reqdep = [('CMake',env.env['system']['general']['cmake_version'])]
        for lang,info in env.env['system']['langs'].items():
            if not info:
                continue
            if info['cased']!='Fortran':
                reqdep += [(info['cased'],info['compiler_version_short'])]
                for dep in info['dep_versions'].split(';'):
                    reqdep += [tuple(dep.split('##',1))]
            else:
                assert not info['dep_versions']#If allowed, we would need to print them somewhere

        print('  System                           : %s'%env.env['system']['general']['system'])
        cp=env.env['cmake_printinfo']
        unused_vars = set(cp['unused_vars'])
        unused_vars_withvals=[]
        ucvlist = []
        for k,v in cfgvars.items():
            if k in unused_vars:
                ucvlist+=['%s%s=%s%s'%(col_bad,k,shlex.quote(v),col_end)]
                unused_vars_withvals+=[ucvlist[-1]]
            else:
                ucvlist+=['%s=%s'%(k,shlex.quote(v))]

        print('  User configuration variables[*]  : %s'%formatlist(ucvlist,None))
        print('  Required dependencies            : %s'%formatlist(['%s[%s]'%(k,v) for k,v in sorted(set(reqdep))],None))
        print('  Optional dependencies present    : %s'%formatlist(['%s[%s]'%(e,env.env['extdeps'][e]['version']) for e in extdeps_avail],
                                                                           col_ok))
        print('  Optional dependencies missing[*] : %s'%formatlist(extdeps_missing,col_bad))
        pkgtxt_en ='%s%i%s package%s built successfully'%(col_ok if n_enabled else '',
                                                          n_enabled,
                                                          col_end if n_enabled else '',
                                                          '' if n_enabled==1 else 's')
        pkgtxt_dis='%s%i%s package%s skipped due to [*]'%(col_bad if n_disabled else '',
                                                          n_disabled,
                                                          col_end if n_disabled else '',
                                                          '' if n_disabled==1 else 's')
        print('  %s : %s'%(pkgtxt_en.ljust(32+(len(col_end)+len(col_ok) if n_enabled else 0)),formatlist(pkg_enabled,col_ok)))
        print('  %s : %s'%(pkgtxt_dis.ljust(32+(len(col_end)+len(col_bad) if n_disabled else 0)),formatlist(pkg_disabled,col_bad)))
        print()
        if unused_vars_withvals:
            print('%sWARNING%s Unused user cfg variables  : %s'%(col_bad,col_end,formatlist(unused_vars_withvals,None)))
            print()
        if cp['other_warnings'] or ( len(cp['unused_vars'])>len(unused_vars_withvals)):
            print('%sWARNING%s unspecified warnings from CMake encountered during environment inspection!'%(col_bad,col_end))
            print()

    if opt.runtests:
        assert (conf.test_dir().parent / '.sbbuilddir').exists()
        import shutil
        shutil.rmtree(conf.test_dir(),ignore_errors=True)
        _testfilter=''
        if opt.testfilter:
            _testfilter=[fltr.strip() for fltr in opt.testfilter.split(',') if fltr.strip()]
        from .testlauncher import perform_tests
        ec = perform_tests( testdir = dirs.testdir,
                            installdir = dirs.installdir,
                            njobs = opt.njobs,
                            prefix = prefix,
                            nexcerpts = opt.nexcerpts,
                            filters = _testfilter,
                            do_pycoverage = False,
                            pkgloader = pkgloader )

        if ec==0 and (cp['unused_vars'] or cp['other_warnings']):
            #Make sure user sees these warnings:
            print('%sWARNING%s There were warnings (see above)'%(col_bad,col_end))
            print()
        if ec:
            sys.exit(ec)


    if not opt.quiet:
        if legacy_mode and cfgvars.get('ONLY','')=='Framework::*' and 'NOT' not in cfgvars:
            print("%sNote that only Framework packages were enabled by default:%s"%(col.bldmsg_notallselectwarn,col.end))
            print()
            print("%s  - To enable pkgs for a given project do: simplebuild -p<projectname>%s"%(col.bldmsg_notallselectwarn,col.end))
            print("%s  - To enable all pkgs do: simplebuild -a%s"%(col.bldmsg_notallselectwarn,col.end))
            print()

        from .envsetup import calculate_env_setup
        if not legacy_mode and not prevent_env_setup_msg and calculate_env_setup():
            print(f'{col.warnenvsetup}Build done. To use the resulting environment you must first enable it!{col.end}')
            print()
            print(f'{col.warnenvsetup}Type the following command (exactly) to do so (undo later by --env-unsetup instead):{col.end}')
            print()
            print(f'    {col.warnenvsetup}eval "$({progname} --env-setup)"{col.end}')
            print()
        else:
            print("Build done. You are all set to begin using the software!")
            print()
            print(f'To see available applications, type "{conf.runnable_prefix}" and hit the TAB key twice.')
            print()
