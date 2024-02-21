#Standalone utilities, which can be safely used without side-effects (e.g. for
#sphinx extensions):
import re

def _find_pkg_dirs_under_basedir( basedir,
                                  cfgfilename,
                                  error_fct = None ):
    def _error( msg ):
        if error_fct is None:
            from . import error
            error.error(msg)
        else:
            error_fct(msg)

    if not basedir.is_dir():
        _error('Asked to search non-existing directory for'
               f' packages: {basedir}')

    #Ignore simplebuild's own cache dirs:
    if any( ( basedir / fn ).exists()
            for fn in ('.sbinstalldir','.sbbuilddir') ):
        return []
    def _norm( p ):
        return p.absolute().resolve()
    if ( basedir / cfgfilename ).exists():
        #basedir is itself a pkg dir
        return [ _norm(basedir) ]

    #dir is not a pkg dir so check sub-dirs:
    pkg_dirs = []
    seen_lc = set()
    for p in basedir.iterdir():
        pl = p.name.lower()
        if not pl or pl[0]=='.' or '~' in pl or '#' in pl:
            continue#always ignore hidden dirs and weird files
        if pl in seen_lc:
            _error('Directory (and file) names differing only in'
                   ' casing are not allowed, due to being a potential'
                   ' source of error on some file systems. \nProblem'
                   f' occured with {p.name} in the directory {basedir}')
        seen_lc.add( pl )
        if p.is_dir():
            pkg_dirs+=_find_pkg_dirs_under_basedir(p,
                                                   cfgfilename,
                                                   error_fct)
    return pkg_dirs

def find_pkg_dirs_under_basedir( basedir, error_fct = None ):
    if error_fct is None:
        def error_fct( msg ):
            raise RuntimeError(msg)
    return _find_pkg_dirs_under_basedir( basedir, 'pkg.info', error_fct )

_nameval_pattern='^[a-zA-Z][a-zA-Z0-9_]{2,24}$'
_nameval=re.compile(_nameval_pattern).match
_nameval_descr=( f'Valid names follow pattern {_nameval_pattern}, contain no'
                 ' duplicate underscores and is not "_simple_build_system"' )

def pkgname_valid(n):
    return _nameval(n) and '__' not in n and n != '_simple_build_system'

def pkgname_valid_or_errmsg(n):
    if not pkgname_valid(n):
        return 'Invalid package name: "%s". %s.'%(n,_nameval_descr)
