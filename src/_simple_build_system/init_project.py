def init_project( depbundles = None ):
    from .io import print
    import pathlib
    cwd = pathlib.Path.cwd()
    template = ( pathlib.Path(__file__).parent
                 / 'data' / 'cfgtemplate.txt' ).read_text()
    res = ''
    for e in template.splitlines():
        res += e.rstrip()+'\n'
        if depbundles and e.startswith('[depend]'):
            #inject depend.projects list:
            sbundles = "', '".join(depbundles)
            res += f"\n  projects = ['{sbundles}']\n\n"

    for f in cwd.glob('**/simplebuild*.cfg'):
        from .error import error
        error('Can not initialise simplebuild package bundle'
              f' here due to conflicting file: {f}')

    outfile = cwd / 'simplebuild.cfg'
    outfile.write_text(res)
    print(f'Created {outfile.name}. If you wish you can edit it to'
          ' fine-tune your configuration')
