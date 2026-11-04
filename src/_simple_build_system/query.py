# The --grep, --find and --replace queries (and their variants). These only
# need to locate the packages and read their pkg.info files, and thus do not
# perform the configuration step of a build (no lock, no cmake inspection of the
# environment, no makefiles), and never modify the cache directory.

def run_query( opt, parser ):
    import pathlib
    from . import loadpkgs
    from . import dirs
    from . import conf
    from . import envcfg
    from . import utils
    from .io import print

    pkgloader = loadpkgs.PackageLoader( loadpkgs.find_pkg_dirs( dirs.pkgsearchpath ),
                                        envcfg.var.pkg_filter,
                                        autodeps = conf.autodeps,
                                        load_all = True )

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

    from .querypattern import create_matcher

    if opt.grep:
        qp = query_pkgs()
        matcher = create_matcher( opt.grep, opt.query_ignorecase )
        print("Grepping %i packages for pattern \"%s\""%(len(qp),opt.grep))
        print()
        n=0
        from . import grep
        for pkg,filenames in qp:
            n += grep.grep( pkg,
                            matcher,
                            filenames = filenames,
                            countonly = opt.grepc )
        print()
        print("Found %i match%s"%(n,'' if n==1 else 'es'))
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
        print("Performed %i replacement%s"%(n,'' if n==1 else 's'))
        raise SystemExit

    if opt.find:
        qp = query_pkgs()
        pattern = opt.find
        matcher = create_matcher( pattern, opt.query_ignorecase )
        from . import find
        print()
        print("Finding files and paths matching \"%s\""%(opt.find))
        print()
        n = 0
        for pkg,filenames in qp:
            m = matcher
            if pattern.startswith( pkg.name +'/' ) and pattern.count('/')==1:
                #Patterns like "PkgName/bla" simply search for "bla" in the
                #package PkgName:
                m = create_matcher( pattern.split('/',1)[1], opt.query_ignorecase )
            n += find.find( pkg, m, filenames = filenames )
        print()
        print("Found %i match%s"%(n,'' if n==1 else 'es'))
        raise SystemExit
