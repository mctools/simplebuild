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
    import sys
    import os
    import pathlib

    if argv  is None:
        argv = sys.argv[:]



    progname = os.path.basename( argv[0] )
    prefix = _io.print_prefix
    print = _io.print

    from . import dirs
    simplebuild_pkg_dirs = [dirs.projdir, *dirs.extrapkgpath]

    from .parse_args import parse_args
    parser, opt = parse_args(
        return_parser = True,
        simplebuild_pkg_dirs = simplebuild_pkg_dirs
    )

    if opt.show_version:
        from . import _determine_version
        sys.stdout.write(_determine_version.determine_version()+'\n')
        raise SystemExit

    if opt.quiet:
        _io.make_quiet()

    if opt.env_setup:
        from .envsetup import emit_envsetup
        emit_envsetup()
        raise SystemExit

    if opt.env_unsetup:
        from .envsetup import emit_env_unsetup
        emit_env_unsetup()
        raise SystemExit

    if opt.summary:
        print("FIXME: summary mode is not yet implemented!")
        raise SystemExit

    if opt.init:
        print("FIXME: init mode is not yet implemented!")
        raise SystemExit

    #setup lockfile:
    from . import dirs
    from . import conf
    from . import envcfg
    from . import utils

    if not dirs.blddir.exists() and not dirs.installdir.exists():
        #Silently set this in case of completely fresh build, to avoid getting
        #some slightly confusing printouts later:
        opt.insist = True

    if opt.removelock and dirs.lockfile.exists():
        os.remove(dirs.lockfile)

    lockfile_content = str(os.getpid())
    if dirs.lockfile.exists():
        locking_pid = dirs.lockfile.read_text()
        error.error('ERROR: Presence of lock file indicates competing invocation of '
                    f'{progname} (by pid {locking_pid}). Force removal'
                    f' with {progname} --removelock if you are sure this is incorrect.')
    dirs.create_bld_dir()
    dirs.lockfile.write_text(lockfile_content)

    assert dirs.lockfile.read_text()==lockfile_content

    def unlock():
        expected_content = lockfile_content
        from os import remove
        from .dirs import lockfile
        if lockfile.exists() and lockfile.read_text()==expected_content:
            remove(lockfile)
    import atexit
    atexit.register(unlock)

    if opt.clean:
        if dirs.blddir.is_dir() or dirs.installdir.is_dir():
            if not opt.quiet:
                print("Removing temporary cache directories. Exiting.")
            conf.safe_remove_install_and_build_dir()
        else:
            if not opt.quiet:
                print("Nothing to clean. Exiting.")
        raise SystemExit

    #Detect changes to system cmake or python files and set opt.examine or opt.insist as appropriate.
    from . import mtime
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

    if opt.insist:
        conf.safe_remove_install_and_build_dir()
        dirs.create_bld_dir()

    utils.pkl_dump(systs,dirs.systimestamp_cache)

    select_filter = envcfg.var.pkg_filter
    assert select_filter is not None
    autodisable = True

    from . import backend

    err_txt,unclean_exception = None,None
    error.default_error_type = error.Error
    try:
        pkgloader = backend.perform_configuration(select_filter=select_filter,
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
                pkg=pkgloader.name2pkg.get(i[0],None) if len(i)==3 else None
                if pkg:
                    return _val_incinfofn(dirs.pkg_dir(pkg,i[1],i[2]))
                else:
                    parser.error("File not found: %s"%fn)
            if os.path.isdir(fn):
                parser.error("Not a file: %s"%fn)
            fn=os.path.abspath(os.path.realpath(fn))
            p = pathlib.Path(fn).absolute().resolve()
            if not any( utils.path_is_relative_to(p,d) for d in simplebuild_pkg_dirs):
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
        print('Successfully built and installed all enabled packages!')
        print()
        print('Summary:')
        print()
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
                    out += '\n%s                                      %s%s%s'%(prefix,colbegin,s,colend)
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

        print('  Required dependencies            : %s'%formatlist(['%s[%s]'%(k,v) for k,v in sorted(set(reqdep))],None))
        print('  Optional dependencies present    : %s'%formatlist(['%s[%s]'%(e,env.env['extdeps'][e]['version']) for e in extdeps_avail],
                                                                           col_ok))
        print('  Optional dependencies missing[*] : %s'%formatlist(extdeps_missing,col_bad))
        print('  Package filters[*]               : <TODO>')
        print('')
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
        if cp['other_warnings'] or len(cp['unused_vars'])>0:
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
        from .envsetup import calculate_env_setup
        needs_env_setup = bool(calculate_env_setup())
        if not prevent_env_setup_msg and needs_env_setup:
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
