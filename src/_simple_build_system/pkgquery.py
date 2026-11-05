# The --pkginfo, --pkggraph, --activegraph, --incinfo and --includecosts
# queries. Like the queries in query.py, these only need to locate the packages
# and read their pkg.info files, and thus do not perform the configuration step
# of a build (no lock, no cmake inspection of the environment, no makefiles).
# The results of a previous inspection of the environment are used if
# available (to know which external dependencies are present, and thus which
# packages are disabled).

def is_pkg_query( opt ):
    return bool( opt.pkginfo or opt.pkggraph or opt.incinfo
                 or opt.includecosts is not None )

def load_pkgs_for_query():
    """Load all packages, and disable those with missing external dependencies
    if the environment was already inspected. Returns (pkgloader, envdict),
    where envdict is None if the environment was not inspected."""
    from . import loadpkgs
    from . import dirs
    from . import conf
    from . import envcfg
    from . import env
    from .backend import load_envcache
    pkgloader = loadpkgs.PackageLoader( loadpkgs.find_pkg_dirs( dirs.pkgsearchpath ),
                                        envcfg.var.pkg_filter,
                                        autodeps = conf.autodeps,
                                        load_all = True )
    envdict = load_envcache() if dirs.envcache.exists() else None
    if envdict is not None:
        env.env = envdict
        _missing = set( k for k,v in envdict['extdeps'].items() if not v['present'] )
        if _missing:
            pkgloader.disable_pkgs_with_extdeps( _missing )
    return pkgloader, envdict

def run_pkg_query( opt, parser ):
    import os
    import sys
    import pathlib
    from . import dirs
    from . import utils
    from .io import print
    pkgloader, envdict = load_pkgs_for_query()

    if opt.includecosts is not None:
        from .includecosts import print_report as print_includecosts
        print_includecosts( pkgloader, dirs.blddir, opt.includecosts )
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
        dirs.create_bld_dir()
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
