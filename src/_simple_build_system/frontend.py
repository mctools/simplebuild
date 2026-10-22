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

    #Select build variant before anything triggers the loading of envcfg:
    from . import variant
    variant.select( variant.from_argparse_result( opt ) )

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

    _interactive_report = bool( opt.testreport and opt.testreport['interactive'] )
    if ( ( opt.reflogupdate or _interactive_report )
         and not ( sys.stdin.isatty() and sys.stdout.isatty() ) ):
        _ = '--reflogupdate' if opt.reflogupdate else '--testreport=interactive'
        error.error(f'The {_} option requires an interactive terminal')

    #setup lockfile:
    from . import dirs

    fresh_cachedir = not dirs.blddir.exists() and not dirs.installdir.exists()
    if fresh_cachedir:
        #Silently set this in case of completely fresh build, to avoid getting
        #some slightly confusing printouts later:
        opt.insist = True

    if opt.removelock and dirs.lockfile.exists():
        os.remove(dirs.lockfile)

    from . import envcfg
    from . import cachedirs
    if envcfg.var.build_cachedir_from_env:
        #The name of the cache dir contains a hash of the path to the
        #simplebuild.cfg file, so it should never be used by another bundle
        #(this would require a hash collision, or a manually copied
        #directory):
        _owner = cachedirs.read_cachedir_owner( envcfg.var.build_cachedir )
        if _owner and _owner != str(envcfg.var.main_cfg_file_resolved):
            error.error(f'The cache directory {envcfg.var.build_cachedir} (placed'
                        f' due to the {envcfg.cache_root_envvar} environment'
                        f' variable) is already used by {_owner}. Please remove it'
                        ' manually.')

    from . import lockfile
    #Make sure the lock is also released when the process is terminated:
    lockfile.exit_cleanly_on_termination_signals()
    dirs.create_bld_dir()
    def _on_stale_lock( info ):
        print(f'Removing stale lock file (created {info.describe()} which is'
              ' no longer running).')
    #A parent process holding the lock can let us use it (this is used when
    #rebuilding from within "sb --reflogupdate"):
    _inherited = os.environ.pop( _inherited_lock_envvar, None )
    _info = lockfile.read_lock( dirs.lockfile ) if _inherited else None
    if _info is not None and _info.content == _inherited:
        _ok, _ = True, _inherited
    else:
        _inherited = None
        _ok, _ = lockfile.acquire( dirs.lockfile, on_stale_removal = _on_stale_lock )
    if not _ok:
        error.error('Presence of lock file indicates competing invocation of '
                    f'{progname} ({_.describe()}). Force removal'
                    f' with {progname} --removelock if you are sure this is incorrect.')
    lockfile_content = _

    def unlock():
        if not _inherited:
            lockfile.release( dirs.lockfile, lockfile_content )
    import atexit
    atexit.register(unlock)

    cachedirs.record_cachedir_owner( envcfg.var.build_cachedir,
                                     envcfg.var.main_cfg_file_resolved )

    from . import conf
    from . import envcfg
    from . import cachedirs

    if opt.testreport is not None and not opt.runtests and _interactive_report:
        ec = _interactive_testreport( opt, lockfile_content )
        unlock()
        sys.exit(ec)

    if opt.testreport is not None and not opt.runtests:
        #Report results of the last test run, without building anything:
        from .testlauncher import print_report
        ec = print_report( dirs.testdir, dirs.installdir / 'tests' / 'testref',
                           opt.nexcerpts, opt.testreport,
                           filters = _parse_testfilter( opt.testfilter )[0],
                           post_factum = True )
        unlock()
        sys.exit(ec)

    if opt.reflogupdate and not opt.runtests:
        #Review the results of the last test run, without building anything:
        ec = _reflogupdate( opt, lockfile_content )
        unlock()
        sys.exit(ec)

    if opt.clean:
        #Remove the cache dirs of all build variants (not just the selected
        #one):
        dcache = envcfg.var.build_cachedir
        removed, skipped = cachedirs.remove_all( dcache, dirs.blddir )
        if not opt.quiet:
            if removed and not ( fresh_cachedir and len(removed)==1
                                 and removed[0].blddir == dirs.blddir ):
                print("Removing temporary cache directories.")
            elif not skipped:
                print("Nothing to clean. Exiting.")
        for cd in skipped:
            error.warn('Not removing cache directories which are in use by a'
                       ' running process or which do not look like they were'
                       f' created by simplebuild: {cd.blddir} {cd.installdir}')
        #Let us perhaps also try and remove the cachedir, i.e. the parent dir of
        #install and build. We want to remove it to not litter an empty
        #"simplebuild_cache" in peoples bundle dirs, but we also do not want to
        #remove a directory which a user might have created manually for their
        #cache (even if empty, since it might still be confusing). As a
        #compromise, we remove it only if it is in the default location with
        #the default name (users messing with pkg_root or cachedir are anyway
        #expected to be more advanced):
        #The cache dirs placed due to SIMPLEBUILD_CACHE_ROOT are removed as
        #well (they are not created manually by users):
        _owner_file = dcache / cachedirs.cfgpath_filename
        if dcache.is_dir() and [ f.name for f in dcache.iterdir() ] == [ _owner_file.name ]:
            _owner_file.unlink()
        if ( ( envcfg.var.build_cachedir_from_env or
               dcache == ( envcfg.var.main_bundle_pkg_root / 'simplebuild_cache' ) )
             and dcache.is_dir() and not any( dcache.iterdir() ) ):
            dcache.rmdir()
        raise SystemExit

    #Remove the least recently used cache dirs of other build variants, if
    #there are too many:
    for cd in cachedirs.remove_least_recently_used(
            envcfg.var.build_cachedir, dirs.blddir,
            envcfg.var.build_max_cachedirs ):
        print('Removed least recently used cache directories'
              f' (build.max_cachedirs={envcfg.var.build_max_cachedirs}):'
              f' {cd.name()}')

    if envcfg.var.extra_cflags or envcfg.var.extra_ldflags:
        if not opt.query_mode:
            _ = envcfg.var.extra_flags_summary_string
            error.warn(f'The simplebuild cfg file specifies extra flags ({_}).'
                       f' Use "{progname} -x" to build without them.')

    #Detect changes to system cmake or python files and set opt.examine or opt.insist as appropriate.
    from . import mtime
    from . import utils
    systs = (mtime.mtime_cmake(),mtime.mtime_pymods())
    oldsysts = utils.pkl_load_or_none(dirs.systimestamp_cache)
    if not isinstance(oldsysts,tuple) or len(oldsysts)!=2:
        if not opt.insist:
            print("Performing complete rebuild since the timestamp cache"
                  " is missing or broken.")
            opt.insist=True
        oldsysts = (None,None)

    #Also make sure the package database can be loaded (otherwise we can no
    #longer be sure what is in the cache, and must start from scratch):
    _dbfile = dirs.blddir / 'globdb.pkl'
    if not opt.insist and _dbfile.exists() and utils.pkl_load_or_none(_dbfile) is None:
        print("Performing complete rebuild since the package database is broken.")
        opt.insist = True

    #The layout of the cache directories might be different in other versions
    #of simplebuild:
    _layoutfile = dirs.blddir / 'layout_version.txt'
    def _read_layout_version():
        try:
            return _layoutfile.read_text().strip()
        except (OSError,UnicodeDecodeError):
            return None
    if not opt.insist and _dbfile.exists():
        if _read_layout_version() != dirs.cache_layout_version:
            print("Performing complete rebuild since the cache directory was"
                  " created by a different version of simplebuild.")
            opt.insist = True

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

    from .backend import load_envcache
    envdict = None if opt.insist else load_envcache()
    if envdict is not None:
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
        #The lockfile was removed along with the build dir, so recreate it:
        dirs.lockfile.write_text(lockfile_content)

    if _read_layout_version() != dirs.cache_layout_version:
        utils.write_atomic( _layoutfile, dirs.cache_layout_version + '\n' )
    cachedirs.touch_last_used( dirs.blddir )
    if envcfg.var.extra_cflags or envcfg.var.extra_ldflags:
        cachedirs.write_extra_flags_file( dirs.blddir,
                                          envcfg.var.extra_cflags,
                                          envcfg.var.extra_ldflags )

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
        from .io import print_error
        print_error("\n\nERROR during configuration:\n\n  %s\n\n"
                    "Aborting."%(err_txt.replace('\n','\n  ')))
        #NB: The package database is not saved, so the next invocation will
        #redo everything which was not completed (as is also the case for
        #KeyboardInterrupt exceptions, which are simply passed on).
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
            #Package names are unique also when ignoring case (this is
            #enforced in loadpkgs.py), so we can safely be relaxed about
            #casing:
            _ = [ p for n,p in pkgloader.name2pkg.items()
                  if n.lower() == opt.pkginfo.lower() ]
            pkg = _[0] if len(_)==1 else None
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

    #Unless in quiet mode (where only errors are printed, on stderr), the
    #complete output goes to stdout, so compilation errors appear in the right
    #place when the output is redirected to a file:
    _redirect = '' if opt.quiet else ' 2>&1'
    ec = utils.system(f'cd {dirs.makefiledir} && '
                      'make --warn-undefined-variables -f Makefile'
                      f' -j{opt.njobs}{extramakeopts}{_redirect}')
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
        utils.remove_within( conf.test_dir(), conf.build_dir() )
        _testfilter, do_pycoverage = _parse_testfilter( opt.testfilter )
        from .testlauncher import perform_tests
        ec = perform_tests( testdir = dirs.testdir,
                            installdir = dirs.installdir,
                            njobs = opt.njobs,
                            nexcerpts = opt.nexcerpts,
                            filters = _testfilter,
                            do_pycoverage = do_pycoverage,
                            pkgloader = pkgloader,
                            report_spec = opt.testreport,
                            interactive_ui = lambda run, stop_on_quit :
                            _interactive_session( opt, lockfile_content, run,
                                                  stop_on_quit ),
                            start_interactive = _interactive_report,
                            test_order = opt.testorder,
                            test_time = opt.testtime )
        if _interactive_report:
            ec = _print_testreport_after_session( opt )
        if opt.reflogupdate:
            _reflogupdate( opt, lockfile_content )

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

    #Release the lock already now, since the caller might continue to run for a
    #long time (e.g. sbrun launching a command):
    unlock()

def _parse_testfilter( testfilter ):
    """Parse value of --testfilter into a list of patterns (or None) and a flag
    indicating whether coverage testing was requested (by the special entry
    "COVERAGE")."""
    patterns = [ e.strip() for e in ( testfilter or '' ).split(',') if e.strip() ]
    do_pycoverage = 'COVERAGE' in patterns
    patterns = [ e for e in patterns if e != 'COVERAGE' ]
    return ( patterns or None ), do_pycoverage

_inherited_lock_envvar = 'SIMPLEBUILD_INHERITED_LOCK'

def _rerun_and_rebuild_fcts( lockfile_content ):
    """Functions for running a test again, and for rebuilding, from within the
    interactive user interfaces."""
    import os
    import sys
    import subprocess
    from . import dirs
    from .testlauncher import rerun_test

    def rerun( name ):
        return rerun_test( dirs.testdir, dirs.installdir, dirs.blddir, name )

    def rebuild():
        #Rebuild in a child process (with the same build variant), letting it
        #use the lock we are holding:
        from . import variant
        vf = variant.selected()
        args = ( [ vf.mode_flag() ] if vf.mode else [] ) + (
            [ '-x' ] if vf.ignore_extra_flags else [] )
        code = ( 'import sys; sys.argv[0] = "sb"; from'
                 ' _simple_build_system._cli import main; main()' )
        env = dict( os.environ )
        env[_inherited_lock_envvar] = lockfile_content
        #Show the output, but also keep it in a log file (so it can be inspected
        #after returning to the user interface):
        p = subprocess.Popen( [ sys.executable, '-c', code, '--quiet' ] + args,
                              env = env, stdout = subprocess.PIPE,
                              stderr = subprocess.STDOUT )
        with rebuild.log_path.open( 'wb' ) as fh:
            for line in p.stdout:
                fh.write( line )
                sys.stdout.buffer.write( line )
                sys.stdout.flush()
        return p.wait() == 0
    rebuild.log_path = dirs.blddir / 'rebuild_output.log'

    return rerun, rebuild

def _print_updated_reflogs( updated_files ):
    import os
    from . import io as _io
    n = len( updated_files )
    _io.print('Updated %i reference log%s%s'%( n, '' if n == 1 else 's',
                                                ':' if n else '.' ))
    for f in updated_files:
        try:
            f = os.path.relpath( f )
        except ValueError:
            pass
        _io.print(f'    {f}')

def _interactive_session( opt, lockfile_content, run = None,
                          stop_on_quit = True ):
    """Interactive test report. If run is given, it is a BackgroundTestRun
    object with tests running in the background."""
    from . import dirs
    from .testlauncher import ( load_results, packages_changed_since,
                                BackgroundTestRun )
    from .testreportui import InteractiveReport, run_interactive_report
    rerun, rebuild = _rerun_and_rebuild_fcts( lockfile_content )
    runinfo, _ = load_results( dirs.testdir )
    if runinfo is None:
        return
    def start_run( names ):
        r = BackgroundTestRun( dirs.testdir, dirs.installdir, dirs.blddir,
                               names, opt.njobs, order = opt.testorder )
        r.start()
        return r
    changed = packages_changed_since( runinfo )
    warning = ( 'WARNING: The results might be outdated, since these packages'
                ' were changed after the tests were run: ' + ' '.join(changed)
                if changed else None )
    spec = opt.testreport or dict( sort = None, failedonly = False,
                                   interactive = True )
    report = InteractiveReport( dirs.testdir, dirs.installdir, spec,
                                _parse_testfilter( opt.testfilter )[0],
                                warning, rerun, rebuild, run = run,
                                start_run_fct = start_run )
    report.stop_on_quit = stop_on_quit
    try:
        run_interactive_report( report )
    finally:
        if report.updated_files:
            _print_updated_reflogs( report.updated_files )

def _print_testreport_after_session( opt ):
    from . import dirs
    from .testlauncher import print_report
    spec = dict( opt.testreport, interactive = False )
    return print_report( dirs.testdir, dirs.installdir / 'tests' / 'testref',
                         opt.nexcerpts, spec,
                         filters = _parse_testfilter( opt.testfilter )[0],
                         post_factum = True )

def _interactive_testreport( opt, lockfile_content ):
    """Interactive test report, followed by the usual report. Returns exit
    code."""
    _interactive_session( opt, lockfile_content )
    return _print_testreport_after_session( opt )

def _reflogupdate( opt, lockfile_content ):
    """Interactive review and update of reference logs. Returns exit code."""
    import sys
    from . import dirs
    from . import error
    from . import io as _io
    from .reflogupdate import Session
    if not ( sys.stdin.isatty() and sys.stdout.isatty() ):
        error.error('The --reflogupdate option requires an interactive terminal')
    rerun, rebuild = _rerun_and_rebuild_fcts( lockfile_content )
    session = Session( dirs.testdir, dirs.installdir,
                       filters = _parse_testfilter( opt.testfilter )[0],
                       rerun_fct = rerun, rebuild_fct = rebuild )
    if not session.has_results:
        _io.print('No test results are available for this build variant'
                  ' (run tests with "-t" first).')
        return 1
    if session.nfailed_jobs:
        _io.print(f'Note: Ignoring {session.nfailed_jobs} tests with reference'
                  ' logs which failed to run.')
    if not session.candidates:
        _io.print('There are no reference logs which differ from the output'
                  ' of the tests.')
        return 0
    from .reflogui import run_reflogupdate
    try:
        run_reflogupdate( session )
    finally:
        _print_updated_reflogs( session.updated_files )
    return 0
