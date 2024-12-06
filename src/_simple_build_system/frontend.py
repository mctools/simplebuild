# Build script which is intended to make the following steps smooth, painless
# and efficient for users:
#
#  1) Detect environment with cmake
#  2) Configuration step
#  3) Build step
#  4) Install step
#  5) Test launch.
#
# Most importantly, it is intended that minimal cpu time is used to needless
# redo work in steps 1-4 above when user changes code or configuration.

def simplebuild_main( argv = None, prevent_env_setup_msg = False ):

    from . import error
    error.fmt_simplebuild_warnings()#as early as possible
    from . import io as _io
    print = _io.print
    import sys
    import os
    import pathlib

    if argv  is None:
        argv = sys.argv[:]

    progname = os.path.basename( argv[0] )

    from .parse_args import parse_args
    parser, opt = parse_args( argv = argv,
                              return_parser = True )

    if opt.show_version:
        from . import _determine_version
        sys.stdout.write(_determine_version.determine_version()+'\n')
        raise SystemExit

    if opt.quiet:
        _io.make_quiet()
    if opt.verbose:
        _io.make_verbose()

    if opt.env_setup:
        #should actually have been done in _cli.py already
        _io.make_quiet()
        from .envsetup import emit_envsetup
        emit_envsetup()
        raise SystemExit

    if opt.env_unsetup:
        #should actually have been done in _cli.py already
        _io.make_quiet()
        from .envsetup import emit_env_unsetup
        emit_env_unsetup()
        raise SystemExit

    if opt.init is not None:
        from . import init_project
        init_project.init_project( args = opt.init )
        raise SystemExit

    # Now undo the effect of --env-setup on the current environment, so
    # subsequent cmake/make invocations run in a clean environment, not poluted
    # by our own build folder (this also solves
    # https://github.com/mctools/simplebuild/issues/8). But first we note if we
    # need to later on warn the user about their environment needing sb
    # --env-setup:

    if not opt.quiet and not prevent_env_setup_msg:
        from .envsetup import calculate_env_setup
        needs_env_setup = bool(calculate_env_setup())
    else:
        needs_env_setup = False

    from .envsetup import apply_envunsetup_to_dict
    apply_envunsetup_to_dict( os.environ )

    if opt.export_jsoncmds:
        from . import target_base
        target_base.need_commands_json_export = True

    if opt.summary:
        print("FIXME: summary mode is not yet implemented!")
        raise SystemExit

    #setup lockfile:
    from . import dirs

    if not dirs.blddir.exists() and not dirs.installdir.exists():
        #Silently set this in case of completely fresh build, to avoid getting
        #some slightly confusing printouts later:
        opt.insist = True

    if opt.removelock and dirs.lockfile.exists():
        os.remove(dirs.lockfile)

    lockfile_content = str(os.getpid())
    if dirs.lockfile.exists():
        locking_pid = dirs.lockfile.read_text()
        error.error('Presence of lock file indicates competing invocation of '
                    f'{progname} (by pid {locking_pid}). Force removal'
                    f' with {progname} --removelock if you are sure this is incorrect.')
    dirs.create_bld_dir()
    dirs.lockfile.write_text(lockfile_content)

    assert dirs.lockfile.read_text()==lockfile_content

    def unlock():
        expected_content = lockfile_content
        if ( dirs.lockfile.exists()
             and dirs.lockfile.read_text()==expected_content ):
            dirs.lockfile.unlink()
    import atexit
    atexit.register(unlock)

    from . import conf
    from . import envcfg

    if opt.clean:
        if dirs.blddir.is_dir() or dirs.installdir.is_dir():
            if not opt.quiet:
                print("Removing temporary cache directories.")
            conf.safe_remove_install_and_build_dir()
            #Let us perhaps also try and remove the cachedir, i.e. the parent
            #dir of install and build. We want to remove it to not litter an
            #empty "simplebuild_cache" in peoples bundle dirs, but we also do
            #not want to remove a directory which a user might have created
            #manually for their cache (even if empty, since it might still be
            #confusing). As a compromise, we remove it only if it is in the
            #default location with the default name (users messing with pkg_root
            #or cachedir are anyway expected to be more advanced):
            dcache = envcfg.var.build_dir_resolved.parent
            assert dcache == envcfg.var.install_dir_resolved.parent
            if ( dcache == ( envcfg.var.main_bundle_pkg_root / 'simplebuild_cache' )
                 and not any( dcache.iterdir() ) ):
                 dcache.rmdir()
        else:
            if not opt.quiet:
                print("Nothing to clean. Exiting.")
        raise SystemExit

    #Detect changes to system cmake or python files and set opt.examine or opt.insist as appropriate.
    from . import mtime
    from . import utils
    systs = (mtime.mtime_cmake(),mtime.mtime_pymods())
    try:
        oldsysts = utils.pkl_load(dirs.systimestamp_cache)
    except IOError:
        if not opt.insist:
            if dirs.systimestamp_cache.exists():
                print("Could not load timestamp cache insist due to IOError loading dirs.systimestamp_cache")
            opt.insist=True
        oldsysts = (None,None)

    if envcfg.var.allow_sys_dev:
        #prevent changes in system from triggering rebuilds (for careful system
        #development use):
        systs = oldsysts

    if not opt.insist and oldsysts!=systs:
        if oldsysts[0]!=systs[0]:
            opt.examine = True
        if not opt.insist and oldsysts[1]!=systs[1]:
            print("simple-build-system time stamp changed -> performing complete rebuild for safety.")
            opt.insist = True

    if not opt.insist and dirs.envcache.exists():
        envdict=utils.pkl_load(dirs.envcache)
        #insist rebuilding COMPLETELY from scratch if install or build dirs changed:
        _autoreconf_inst_dir = envdict['_autoreconf_environment'].get('install_dir')
        _autoreconf_bld_dir = envdict['_autoreconf_environment'].get('build_dir')
        if _autoreconf_inst_dir != str(conf.install_dir()):
            print("Performing complete rebuild since the cache install dir changed (%s -> %s)"%(_autoreconf_inst_dir,
                                                                                                str(conf.install_dir())))
            opt.insist = True
        elif _autoreconf_bld_dir != str(conf.build_dir()):
            print("Performing complete rebuild since the cache build dir changed (%s -> %s)"%(_autoreconf_bld_dir,
                                                                                              str(conf.build_dir())))
            opt.insist = True

    if not opt.insist and opt.export_jsoncmds:
        print('Always performing complete rebuild when exporting'
              ' commands to JSON')
        opt.insist=True

    if opt.insist:
        conf.safe_remove_install_and_build_dir()
        dirs.create_bld_dir()

    utils.pkl_dump(systs,dirs.systimestamp_cache)

    select_filter = envcfg.var.pkg_filter
    assert select_filter is not None

    from . import backend

    err_txt,unclean_exception = None,None
    error.default_error_type = error.Error
    try:
        pkgloader = backend.perform_cfg(select_filter=select_filter,
                                        force_reconf=opt.examine,
                                        load_all_pkgs = opt.query_mode,
                                        quiet=opt.quiet,
                                        verbose=opt.verbose,
                                        export_jsoncmds = opt.export_jsoncmds)
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
        #fixme: unprefixed printouts?:
        print("\n\nERROR during configuration:\n\n  %s\n\n"
              "Aborting."%(err_txt.replace('\n','\n  ')))
        #make all packages need reconfig upon next run:
        from . import db
        db.db['pkg2timestamp']={}
        db.save_to_file()
        #exit (with ugly traceback if unknown type of exception):
        if unclean_exception:
            error.print_traceback(unclean_exception)
        sys.exit(1)

    assert dirs.makefiledir.is_dir()

    if opt.requirepkgs:
        _rps = set(opt.requirepkgs)
        _notfound = set( pn for pn in _rps if pn not in pkgloader.name2pkg )
        if _notfound:
            error.error('Unknown package name given to --requirepkg:'
                        f' "{_notfound.pop()}"')

        _actual_pkgs = set( p.name for p in pkgloader.enabled_pkgs_iter() )
        _missing = _rps - _actual_pkgs
        if _missing:
            missinglist = ', '.join(e for e in sorted(_missing))
            nmissing = len(_missing)
            error.error(f'{nmissing} required package'
                        f'{"s" if nmissing!=1 else ""} were not '
                        f'present and enabled: {missinglist}')


    def query_pkgs():
        #returns list of (pkg,filenames) where filenames is None, or a list of
        #the files in the pkg to search (e.g. ['pkg.info','pycpp_bla/mod.cc']
        all_pkgs = list(sorted(pkgloader.pkgs))
        if not opt.querypaths:
            return [(p,None) for p in all_pkgs]
        res=[]
        for p in all_pkgs:
            search_entire_package = False
            filenames=[]
            for qp in opt.querypaths:
                assert isinstance(p.dirname,str)#fixme: to pathlib.Path
                pdir = pathlib.Path(p.dirname)
                if pdir == qp or utils.path_is_relative_to( pdir, qp ):
                    search_entire_package = True
                    break
                if utils.path_is_relative_to( qp, pdir ):
                    filenames.append( qp.relative_to(pdir) )
            if search_entire_package:
                res.append( (p, None) )
            elif filenames:
                res.append( (p, filenames) )
        return res

    if opt.grep:
        qp = query_pkgs()
        print("Grepping %i packages for pattern \"%s\""%(len(qp),opt.grep))
        print()
        n=0
        from . import grep
        for pkg,filenames in qp:
            n += grep.grep( pkg,
                            opt.grep,
                            filenames = filenames,
                            countonly = opt.grepc )
        print()
        print("Found %i matches"%n)
        raise SystemExit

    if opt.replace:
        qp = query_pkgs()
        pattern = opt.replace
        from . import replace
        search_pat, replace_pat = replace.decode_pattern(pattern)
        if not search_pat:
            parser.error("Bad syntax in replacement pattern: %s"%pattern)
        print()
        print("Replacing all \"%s\" with \"%s\""%(search_pat,replace_pat))
        n = 0
        for pkg,filenames in qp:
            n += replace.replace( pkg,
                                  search_pat,
                                  replace_pat,
                                  filenames = filenames )
        print()
        print("Performed %i replacements"%n)
        raise SystemExit

    if opt.find:
        qp = query_pkgs()
        pattern = opt.find
        from . import find
        print()
        print("Finding files and paths matching \"%s\""%(opt.find))
        print()
        n = 0
        for pkg,filenames in qp:
            n += find.find( pkg,
                            pattern = opt.find,
                            filenames = filenames )
        print()
        print("Found %i matches"%n)
        raise SystemExit

    if opt.incinfo:
        import glob
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
                pkg=pkgloader.name2pkg.get(i[0],None) if len(i) in (2,3) else None
                if pkg:

                    if len(i) == 3:
                        return _val_incinfofn( os.path.join(pkg.dirname,i[1],i[2]) )
                    else:
                        return _val_incinfofn( os.path.join(pkg.dirname,'libinc', i[1]) )
                else:
                    parser.error("File not found: %s"%fn)
            if os.path.isdir(fn):
                parser.error("Not a file: %s"%fn)
            fn = os.path.abspath(fn)#NB: We used to do realpath here as well,
                                    #but it gave problems with symlinked source
                                    #files.
            p = pathlib.Path(fn).absolute()#NB: We used to do .resolve() here as
                                           #well
            simplebuild_pkg_dirs = [dirs.main_bundle_pkg_root,
                                    *dirs.extrapkgpath]
            if not any( utils.path_is_relative_to(p,d)
                        for d in simplebuild_pkg_dirs):
                _dirsfmt=('\n '.join(str(e) for e in simplebuild_pkg_dirs))
                parser.error(f'File {p} must be located under one of the '
                             f'following directories:\n{_dirsfmt}')
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
        raise SystemExit

    if opt.pkginfo:
        pkg=pkgloader.name2pkg.get(opt.pkginfo,None)
        if not pkg:
            utils.err('Unknown package "%s"'%opt.pkginfo)
        else:
            pkg.dumpinfo(pkgloader.autodeps)
            raise SystemExit

    if opt.pkggraph:
        dotfile=dirs.blddir / 'pkggraph.dot'
        from . import dotgen
        dotgen.dotgen(pkgloader,dotfile,enabled_only=opt.pkggraph_activeonly)
        if not opt.quiet:
            print('Package dependencies in graphviz DOT format has'
                  ' been generated in %s'%(dotfile))
        ec=utils.system('dot -V > /dev/null 2>&1')
        if ec:
            if not opt.quiet:
                print('Warning: command "dot" not found or ran into problems.')
                print('Please install graphviz to enable graphical'
                      ' dependency displays')
            sys.exit(1)
        pkggraphout = dirs.blddir / 'pkggraph.png'
        import shlex
        ec=utils.system(
            'unflatten -l3 -c7 %s|dot -Tpng -o %s'%(shlex.quote(str(dotfile)),
                                                    shlex.quote(str(pkggraphout)))
        )
        if ec or not pkggraphout.is_file():
            if not opt.quiet:
                print('Error: Problems with dot command while transforming'
                      f' {dotfile.name} to {pkggraphout.name}')
            sys.exit(1)
        else:
            if not opt.quiet:
                print('Package dependencies in PNG format has been generated'
                      ' in %s'%pkggraphout)
        raise SystemExit


    if not opt.njobs:
        from . import cpudetect
        opt.njobs=cpudetect.auto_njobs()

    if not opt.quiet:
        print("Configuration completed => Launching build with %i parallel processes"%opt.njobs)

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

    assert dirs.makefiledir.is_dir()

    ec = utils.system(f'cd {dirs.makefiledir} && '
                      'make --warn-undefined-variables -f Makefile'
                      f' -j{opt.njobs}{extramakeopts}')
    if ec!=0:
        if not opt.quiet:
            print("ERROR: Build problems encountered")
        sys.exit(1 if ec > 128 else ec)

    if not opt.quiet:
        from . import build_summary
        build_summary.produce_build_summary(
            pkgloader = pkgloader,
            verbose = opt.verbose
        )

    if opt.runtests:
        assert (conf.test_dir().parent / '.sbbuilddir').exists()
        import shutil
        shutil.rmtree(conf.test_dir(),ignore_errors=True)
        _testfilter=None
        do_pycoverage = False
        if opt.testfilter:
            _testfilter = [ fltr.strip()
                            for fltr in opt.testfilter.split(',')
                            if fltr.strip() ]
            while 'COVERAGE' in _testfilter:
                _testfilter.remove('COVERAGE')
                do_pycoverage = True
        from .testlauncher import perform_tests
        ec = perform_tests( testdir = dirs.testdir,
                            installdir = dirs.installdir,
                            njobs = opt.njobs,
                            nexcerpts = opt.nexcerpts,
                            filters = _testfilter,
                            do_pycoverage = do_pycoverage,
                            pkgloader = pkgloader )

        from . import env
        from . import col
        cp = env.env['cmake_printinfo']
        if ec==0 and (cp['unused_vars'] or cp['other_warnings']):
            #Make sure user sees these warnings:
            print('%sWARNING%s There were warnings (see above)'%(col.bad,col.end))
            print()
        if ec:
            sys.exit(ec)

    if not opt.quiet:
        if needs_env_setup:
            from . import col
            print(f'{col.warnenvsetup}Build done. To use the resulting environment you must first enable it!{col.end}')
            print()
            print(f'{col.warnenvsetup}Type the following command (exactly) to do so (undo later by --env-unsetup instead):{col.end}')
            print()
            print(f'    {col.warnenvsetup}eval "$({progname} --env-setup)"{col.end}')
            print()
        else:
            print("Build done. You are all set to begin using the software!")
            print()
            if not needs_env_setup:
                print(f'To see available applications, type "{conf.runnable_prefix}" and hit the TAB key twice.')
                print()
