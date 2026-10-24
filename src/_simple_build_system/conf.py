#configuration file (warning: not everything can be changed here without updating other modules as well)

import os
import pathlib
import sysconfig
from . import io as _io

def AbsPath( p ):
    return pathlib.Path(p).expanduser().resolve().absolute()

__cache_pyextsuf = sysconfig.get_config_var('EXT_SUFFIX') #value like '.cpython-311-x86_64-linux-gnu.so' (.so even on osx)

lang_extensions = {
    'cxx' : ( ['hh', 'icc'], ['cc'] ),
    'c' : ( ['h'], ['c'] ),
    'fortran' : ( [], ['f'] ),
}

package_cfg_file='pkg.info'

autodeps = set(['Core'])
projectname='SBLD'
projectname_lc = projectname.lower()
runnable_prefix = 'sb_'

#TODO: Do not repeat .io stuff here:
print_prefix_name = _io.print_prefix_name
print_prefix = _io.print_prefix
def print( *args, **kwargs ):
    return _io.print( *args, **kwargs )
def print_no_prefix( *args, **kwargs ):
    return _io.print_no_prefix( *args, **kwargs )
def make_quiet():
    return _io.make_quiet()

def runnable_name(pkg,base_name):
    #create global runnable name for a runnable in a package:
    return ('%s%s_%s'%(runnable_prefix,pkg.name,base_name)).lower()

def runnable_is_test(runnable_name):
    return runnable_name.split('_',2)[2].startswith('test')

def libldflag(pkg): return '-lPKG__%s'%pkg.name
def namefct_lib(pkg,subdir,platform_pattern): return platform_pattern%('PKG__'+pkg.name)
def namefct_pycpp(pkg,subdir,platform_pattern): return subdir[6:] + __cache_pyextsuf

def namefct_app(pkg,subdir,platform_pattern): return runnable_name(pkg,subdir[4:])

def checkfct_pycpp(pkg,subdir,name):
    n=subdir[6:]
    if n=='__init__':
        return 'The name pycpp___init__/ is forbidden. Instead put compiled init code in a subdir called pycpp__init/'
    cf=os.path.join(pkg.dirname,'python/%s.py'%n)
    if os.path.exists(cf):
        return 'Python module %s.%s is provided in both pure (python/%s.py) and compiled (pycpp_%s/) forms'%(pkg.name,n,n,n)

def descrfct_lib(pkg,subdir,name):
    from . import col
    return col.bldcol('shlib'),'shared library for package %s'%pkg.name

def descrfct_pycpp(pkg,subdir,name):
    from . import col
    return col.bldcol('pymod'),'python module %s.%s'%(pkg.name,subdir[6:])

def descrfct_app(pkg,subdir,name):
    from . import col
    return col.bldcol('app'),'application %s'%name

def pkg_install_dir( pkgname ):
    """Directory in the install area holding files belonging exclusively to
    the package. Currently this is just an "apps" subdirectory, with an empty
    file for each application installed by the package in the shared bin/
    directory."""
    return install_dir() / 'pkgs' / pkgname

def _symlink_owned_by_pkg( f, pkgname ):
    """Whether f is a symlink installed for the given package in one of the
    install directories shared between packages (scripts/ or tests/testref/).
    Such symlinks point to files in the package itself (e.g.
    <blddir>/pkgs/<pkgname>/scripts/<scriptname>). Note that a name pattern like
    "sb_<pkgname>_*" is not enough to determine this, since packages named e.g.
    Foo and Foo_Bar would clash."""
    from . import dirs
    if not f.is_symlink():
        return False
    target = pathlib.Path(os.path.normpath(f.parent / os.readlink(f)))
    return target.parent.parent == dirs.pkg_dir(pkgname)

def _remove_apps_owned_by_pkg( pkgname, names = None ):
    """Remove applications installed in the shared bin/ directory by the
    package (as recorded in the install dir of the package). NB: Applications
    are installed directly in bin/ (rather than e.g. symlinked from there),
    since some applications locate other files (e.g. ../lib) relative to their
    own location."""
    from . import utils
    instdir = install_dir()
    markerdir = pkg_install_dir( pkgname ) / 'apps'
    if not markerdir.is_dir() or markerdir.is_symlink():
        return
    for marker in sorted( markerdir.iterdir() ):
        if names is not None and marker.name not in names:
            continue
        #Apps are files (or on macOS potentially also .dSYM dirs):
        for f in ( marker.name, marker.name + '.dSYM' ):
            utils.remove_within( instdir / 'bin' / f, instdir )
        utils.remove_within( marker, instdir )

def _remove_symlinks_owned_by_pkg( directory, pkgname, names = None ):
    from . import utils
    if not directory.is_dir() or directory.is_symlink():
        return
    for f in sorted(directory.iterdir()):
        if names is not None and f.name not in names:
            continue
        if _symlink_owned_by_pkg( f, pkgname ):
            utils.remove_within( f, install_dir() )

def uninstall_package(pkgname):
    #completely remove all traces of a pkg from the install area. This does not
    #depend on any information in the package database, but only on the
    #layout of the install area (files of a package are either in directories
    #belonging to that package, have names which are unique to the package, are
    #symlinks pointing into the package, or are applications recorded in the
    #install dir of the package):
    from . import utils
    instdir = install_dir()
    if not ( instdir / '.sbinstalldir' ).exists():
        return
    _remove_apps_owned_by_pkg( pkgname )
    for d in ( pkg_install_dir(pkgname),
               instdir / 'data' / pkgname,
               instdir / 'include' / pkgname,
               instdir / 'python' / pkgname ):
        utils.remove_within( d, instdir )
    #NB: Package names never contain "__":
    utils.remove_glob_within( instdir / 'lib', f'*PKG__{pkgname}.*', instdir )
    for d in ( 'scripts', 'tests/testref' ):
        _remove_symlinks_owned_by_pkg( instdir / d, pkgname )

#Get paths to all packages (including the framework and user packages)

def main_bundle_pkg_root():
    from . import envcfg
    return envcfg.var.main_bundle_pkg_root

def extra_pkg_path():
    from . import envcfg
    return envcfg.var.extra_pkg_path_list

def extra_extdep_path():
    from . import envcfg
    return envcfg.var.extra_extdep_path

def pkg_search_path():
    candidates = [main_bundle_pkg_root()]
    candidates.extend(extra_pkg_path())
    dirs = []
    for d in candidates:
        if d not in dirs:
            dirs.append( d )
    return dirs

def build_dir():
    from . import envcfg
    return envcfg.var.build_dir_resolved

def install_dir():
    from . import envcfg
    return envcfg.var.install_dir_resolved

def test_dir():
    return build_dir() / 'testresults/'

def safe_remove_install_and_build_dir():
    from . import utils
    for d in ( build_dir(), install_dir() ):
        utils.remove_cache_dir( d )

def target_factories_for_patterns():
    from . import tfact_symlink as tfs
    from . import tfact_headerdeps as tfh
    from . import tfact_binary as tfb
    ll=[]
    ll += [('data',   tfs.create_tfactory_symlink('','data/%s',chmodx=False))]
    ll += [('scripts',tfs.create_tfactory_symlink('','scripts',chmodx=True,
                                                  renamefct=runnable_name))]#todo: disallow periods? enforce lowercase?
    ll += [('python', tfs.create_tfactory_symlink(r'.+\.py','python/%s',
                                                  chmodx=False))]
    ll += [('pycpp_.+',
            tfb.create_tfactory_binary(shlib=True,
                                       instsubdir='python/%s',
                                       allowed_langs=['cxx'],
                                       namefct=namefct_pycpp,
                                       descrfct=descrfct_pycpp,
                                       checkfct=checkfct_pycpp,
                                       flagfct = lambda pkg,subdir
                                       :['-DPYMODNAME=%s'%subdir[6:]]))]
    #Applications are installed in the shared bin directory (which is in the
    #PATH), and recorded in the install dir of the package:
    ll += [('app_.+', tfb.create_tfactory_binary(instsubdir='bin',
                                                 ownerdir='pkgs/%s/apps',
                                                 namefct=namefct_app,
                                                 descrfct=descrfct_app))]
    ll += [('libsrc', tfb.create_tfactory_binary(pkglib=True,
                                                 namefct=namefct_lib,
                                                 descrfct=descrfct_lib))]
    ll += [('libinc',  tfh.tfactory_headerdeps)]#just for header dependencies

    return ll

def ignore_file(f):
    f = f.name if hasattr(f,'name') else f
    return ( f[0]=='.' or '~' in f or '#' in f or f.endswith('.orig')
             or f.endswith('.bak') or f=='__pycache__' )

def target_factories():
    #non-pattern factories:
    from . import tfact_prepinc
    from . import tfact_pyinit
    from . import tfact_reflogs
    from . import tfact_libavail
    ll = []
    ll += [tfact_prepinc.tfactory_prepinc]
    ll += [tfact_pyinit.tfactory_pyinit]
    ll += [tfact_reflogs.tfactory_reflogs]
    ll += [tfact_libavail.tfactory_libavail]
    return ll

def deinstall_parts(instdir,pkgname,current_parts,disappeared_parts):
    from . import dirs
    from . import utils
    i=instdir
    if not ( i / '.sbinstalldir' ).exists():
        return
    unused=set()
    pydone=False
    pkgcache=dirs.pkg_cache_dir(pkgname)
    def rm_tree(p):
        utils.remove_within( p, i )
    def rm_file( p ):
        utils.remove_within( p, i )
    def rm_cachefile( p ):
        utils.remove_within( p, dirs.blddir )
    def touch_cachefile( p ):
        #Invalidates cached content (if any: the directory is absent e.g. if
        #the package never had a python/ subdir):
        if p.parent.is_dir():
            p.touch()
    def rm_pattern(thedir,pattern):
        utils.remove_glob_within( thedir, pattern, i )

    for d in disappeared_parts:
        if d=='libinc':
            rm_tree( i / 'include' / pkgname)
        elif d=='libsrc':
            rm_pattern(i/'lib','*PKG__%s.*'%pkgname)
        elif d.startswith('app_'):
            _runnable_name='%s%s_%s' %( runnable_prefix,
                                        pkgname.lower(),
                                        d[4:].lower() )
            _remove_apps_owned_by_pkg( pkgname, names = [ _runnable_name ] )
        elif d=='symlink__scripts':
            _remove_symlinks_owned_by_pkg( i / 'scripts', pkgname )
            touch_cachefile( pkgcache/'symlinks'/'scripts.pkl' )
            rm_cachefile(pkgcache/'symlinks'/'scripts.pkl.old')
        elif d=='symlink__data':
            rm_tree( i / 'data' / pkgname )
            touch_cachefile( pkgcache / 'symlinks' / 'data.pkl' )
            rm_cachefile( pkgcache / 'symlinks' / 'data.pkl.old' )
        #don't do this for testref_links, since all packages always have this target:
        #elif d=='testref_links':
        #    NB: Syntax not updated for pathlib and fcts above!:
        #    utils.rm_f(os.path.join(i,'tests/testref/%s%s_*.log'%(runnable_prefix,pkgname.lower())))
        #    utils.touch(os.path.join(pkgcache,'testref/testref.pkl'))
        #    utils.rm_f(os.path.join(pkgcache,'testref/testref.pkl.old'))
        elif d.startswith('autopyinit'):
            if not any(e.startswith('autopyinit') for e in current_parts):
                #we must remove the auto generated __init__.py as it is in the way
                rm_file( i / 'python' / pkgname / '__init__.py' )
                touch_cachefile( pkgcache / 'symlinks' / 'python.pkl' )
                rm_cachefile( pkgcache / 'symlinks' / 'python.pkl.old' )
        elif d.startswith('pycpp_') or d=='symlink__python':
            if d.startswith('pycpp'):
                #NB: Compiled modules have names like
                #mymod.cpython-312-x86_64-linux-gnu.so:
                rm_file( i / 'python' / pkgname / ( d[6:] + __cache_pyextsuf ) )
            if not pydone:
                pydone=True
                if not any((e.startswith('pycpp') or e=='symlink__python') for e in current_parts):
                    rm_tree( i / 'python' / pkgname )
                touch_cachefile( pkgcache / 'symlinks' / 'python.pkl' )
                rm_cachefile( pkgcache / 'symlinks' / 'python.pkl.old' )
                touch_cachefile( pkgcache / 'pyinit' / 'pyinit.pkl' )
                #rm_file( pkgcache / 'pyinit' / 'pyinit.pkl.old' )
        else:
            unused.add(d)
    assert not unused,str(unused)
