def produce_build_summary( *, pkgloader, verbose ):
    from . import dirs
    from . import envcfg
    from .utils import path_is_relative_to
    import pathlib
    import os
    from .io import print, print_prefix as prefix

    print('Summary:')
    print()
    def fixpath( p ):
        if envcfg.var.conda_prefix:
            pabs = p.absolute().resolve()
            cp = pathlib.Path(envcfg.var.conda_prefix).absolute().resolve()
            if cp.is_dir() and path_is_relative_to( pabs, cp ):
                return os.path.join('${CONDA_PREFIX}',str(pabs.relative_to(cp)))
        return str(p)
    print('  Main bundle pkg root             : '
          '%s'%fixpath(dirs.main_bundle_pkg_root))
    print('  Installation directory           : %s'%fixpath(dirs.installdir))
    print('  Build directory                  : %s'%fixpath(dirs.blddir))

    from . import col
    col_ok = col.ok
    col_bad = col.bad
    col_end = col.end
    #FIXME: Use formatlist module!
    def formatlist(lin,col):
        ll=lin[:]
        colbegin = col if col else ''
        colend = col_end if col else ''
        if not ll or ll==['']:
            return '<none>'
        first=True
        out=''
        while ll:
            s=''
            while ll and len(s)<40:
                if s:
                    s += ' '
                s += ll.pop(0)
            if first:
                out+='%s%s%s'%(colbegin,s,colend)
                first=False
            else:
                out += '\n%s                                      %s%s%s'%(prefix,colbegin,s,colend)
        return out
        #return ' '.join(ll)

    pkg_src_info = []
    for basedir in dirs.pkgsearchpath:
        _pkgs_in_basedir = [p for p in pkgloader.pkgs if basedir in p.dirpath.parents]
        pkg_nr = len(_pkgs_in_basedir)
        pkg_enabled = sum(1 for p in _pkgs_in_basedir if p.enabled)
        pkg_src_info.append([basedir, pkg_enabled, (pkg_nr-pkg_enabled) ])

    def pkg_info_str(info):
        p=fixpath(info[0])
        if info[1]+info[2]==0:
            descr='no pkgs'
        else:
            nbuilt = '%s%d%s'%(col_ok,info[1],col_end) if info[1]!=0 else '0'
            if info[2]==0:
                #everything built
                descr=f'{nbuilt} pkgs'
            else:
                nskipped = '%s%d%s'%(col_bad,info[2],col_end)
                descr='%s built, %s skipped'%(nbuilt, nskipped)
        return "%s (%s)"%(p, descr)

    psptxt = '  Package search path              : '
    for idx,info in enumerate(pkg_src_info):
        _= (' '*len(psptxt)) if idx else psptxt
        print(f'{_}{pkg_info_str(info)}')

    nmax = 20
    pkg_enabled = sorted([p.name for p in pkgloader.pkgs if p.enabled])
    n_enabled = len(pkg_enabled)
    lm2='(%i more,'
    limittxt=['...',lm2,'supply','--verbose','to','see','all)']
    if not verbose and n_enabled>nmax:
        limittxt[1] = lm2%(n_enabled-nmax)
        pkg_enabled = pkg_enabled[0:nmax]+limittxt
    pkg_disabled = sorted([p.name for p in pkgloader.pkgs if not p.enabled])
    n_disabled = len(pkg_disabled)
    if not verbose and n_disabled>nmax:
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
    _pfilter = ( '<none>' if envcfg.var.pkg_filter.fully_open()
                 else "'%s'"%envcfg.var.pkg_filter.as_string() )
    print(f"  Package filter[*]                : {_pfilter}")
    print('  Build mode                       : '
          + f'{envcfg.var.build_mode_summary_string}' )


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
