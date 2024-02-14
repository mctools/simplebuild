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
    args, compact = has_keyword(args, 'COMPACT')
    args, build_cachedir = extract_opt_with_args( args, 'CACHEDIR',
                                                  pick_last = True)

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
            if debug_mode:
                #inject mode statement:
                sbundles = "', '".join(depbundles)
                res += "\n  mode = 'debug'\n\n"
            if build_cachedir:
                #inject cachedir statement:
                res += f"\n  cachedir = '{build_cachedir}'\n\n"
        elif e.startswith('[depend]'):
            if depbundles:
                #inject depend.projects list:
                sbundles = "', '".join(depbundles)
                res += f"\n  projects = ['{sbundles}']\n\n"

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
