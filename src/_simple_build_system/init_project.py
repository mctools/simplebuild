def init_project( depbundles = None ):
    #Keywords:
    debug_mode = False
    compact = False
    if 'DEBUG' in depbundles:
        debug_mode = True
        depbundles = [ d for d in depbundles if d!='DEBUG' ]
    if 'COMPACT' in depbundles:
        compact = True
        depbundles = [ d for d in depbundles if d!='COMPACT' ]
    _db = []
    for d in depbundles:
        if d not in _db:
            _db.append(d)
    depbundles = _db

    from .io import print
    import pathlib
    cwd = pathlib.Path.cwd()
    template = ( pathlib.Path(__file__).parent
                 / 'data' / 'cfgtemplate.txt' ).read_text()
    res = ''
    for e in template.splitlines():
        res += e.rstrip()+'\n'
        if debug_mode and e.startswith('[build]'):
            #inject mode statement:
            sbundles = "', '".join(depbundles)
            res += "\n  mode = 'debug'\n\n"
        if depbundles and e.startswith('[depend]'):
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
