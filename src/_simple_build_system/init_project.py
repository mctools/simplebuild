def init_project( args = None ):
    args = args[:] if args else []

    def has_keyword( args, kw ):
        _=[e for e in args if e!=kw]
        return _, len(args)!=len(_)

    def extract_opt_with_args( args, optname, pick_last ):
        key=f'{optname}::'
        optvals = []
        otherargs = []
        for e in args:
            if e.startswith(key):
                optvals.append( e[len(key):] )
            else:
                otherargs.append( e )
        if pick_last:
            optvals = optvals[-1] if optvals else None
        return otherargs, optvals

    #Keywords:
    args, debug_mode = has_keyword(args, 'DEBUG')
    args, release_mode = has_keyword(args, 'RELEASE')
    args, reldbg_mode = has_keyword(args, 'RELDBG' )
    args, compact = has_keyword(args, 'COMPACT')
    args, build_cachedir = extract_opt_with_args( args, 'CACHEDIR',
                                                  pick_last = True)
    args, build_pkgfilter = extract_opt_with_args( args, 'PKGFILTER',
                                                   pick_last = False)

    _n_mode_opts=sum(int(e) for e in (debug_mode,release_mode,reldbg_mode))
    if _n_mode_opts == 0:
        release_mode=True
    elif _n_mode_opts > 1:
        from .error import error
        error('Do not specify more than one of the DEBUG, '
              'RELEASE, and RELDBG keywords')

    #Remaining args are the dep-bundles, but remove duplicates:
    depbundles = []
    for d in args:
        if d not in depbundles:
            depbundles.append(d)

    from .io import print
    import pathlib
    cwd = pathlib.Path.cwd()
    template = ( pathlib.Path(__file__).parent
                 / 'data' / 'cfgtemplate.txt' ).read_text()
    res = ''
    for e in template.splitlines():
        res += e.rstrip()+'\n'
        if e.startswith('[build]'):
            if ( debug_mode or reldbg_mode ):
                #inject mode statement:
                sbundles = "', '".join(depbundles)
                res += "\n  mode = '%s'\n\n"%( 'debug'
                                               if debug_mode
                                               else 'reldbg' )
            if build_cachedir:
                #inject cachedir statement:
                res += f"\n  cachedir = '{build_cachedir}'\n\n"
            if build_pkgfilter:
                #inject pkg_filter statement:
                _ = "','".join(build_pkgfilter)
                res += f"\n  pkg_filter = ['{_}']\n\n"
        elif e.startswith('[depend]'):
            if depbundles:
                #inject depend.bundles list:
                sbundles = "', '".join(depbundles)
                res += f"\n  bundles = ['{sbundles}']\n\n"

    if compact:
        res2 = ''
        for e in res.splitlines():
            if '#' in e:
                e = e.split('#',1)[0]
            e = e.rstrip()
            if e:
                res2 += e + '\n'
        res = res2

    for f in cwd.glob('**/simplebuild*.cfg'):
        from .error import error
        error('Can not initialise simplebuild package bundle'
              f' here due to conflicting file: {f}')

    outfile = cwd / 'simplebuild.cfg'
    outfile.write_text(res)
    print(f'Created {outfile.name}. If you wish you can edit it to'
          ' fine-tune your configuration')
