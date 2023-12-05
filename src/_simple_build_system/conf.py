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

def uninstall_package(pkgname):
    #completely remove all traces of a pkg from the install area:
    #a few sanity checks since we are about to use rm -rf:
    #assert d and not ' ' in d

    instdir = install_dir()
    if not ( instdir / '.sbinstalldir' ).exists():
        return

    #FIXME: <pn>_foo_bar_blah might be script Blah from package Foo_Bar or script
    #Bar_Blah from package Foo. We should check that the symlinks goes to the
    #correct package! (or better yet, simplebuild should produce pickle file in
    #install or bld with all package dependencies and provided scripts, apps,
    #etc.). But a quick fix for the scripts (not for the apps) would be for the
    #framework to remove all symlinks to the package in question from the
    #install dir, and just let the present function deal with non-symlinks.

    parts = [ f'data/{pkgname}',
              f'lib/*PKG__{pkgname}.*',
              f'tests/testref/{runnable_prefix}{pkgname.lower()}_*.log',
              f'include/{pkgname}',
              f'python/{pkgname}',
              f'scripts/{runnable_prefix}{pkgname.lower()}_*',
              f'bin/{runnable_prefix}{pkgname.lower()}_*' ]
    import shutil
    for p in parts:
        for f in instdir.glob(p):
            if f.is_dir():
                shutil.rmtree(f,ignore_errors = True)
            else:
                f.unlink(missing_ok = True)

#Get paths to all packages (including the framework and user packages)

def projects_dir():
    from . import envcfg
    return envcfg.var.projects_dir

def extra_pkg_path():
    from . import envcfg
    return envcfg.var.extra_pkg_path_list

def pkg_search_path():
    #candidates = [framework_dir(), projects_dir()]
    candidates = [projects_dir()]
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
    import shutil
    for fingerprintfile in [ build_dir() / '.sbbuilddir', install_dir() / '.sbinstalldir' ]:
        if fingerprintfile.exists():
            shutil.rmtree( fingerprintfile.parent, ignore_errors=True )

def target_factories_for_patterns():
    from . import tfact_symlink as tfs
    from . import tfact_headerdeps as tfh
    from . import tfact_binary as tfb
    l=[]
    l += [('data',   tfs.create_tfactory_symlink('','data/%s',chmodx=False))]
    l += [('scripts',tfs.create_tfactory_symlink('','scripts',chmodx=True,
                                                 renamefct=runnable_name))]#todo: disallow periods? enforce lowercase?
    l += [('python', tfs.create_tfactory_symlink('.+\.py','python/%s',chmodx=False))]
    l += [('pycpp_.+', tfb.create_tfactory_binary(shlib=True,
                                                  instsubdir='python/%s',
                                                  allowed_langs=['cxx'],
                                                  namefct=namefct_pycpp,
                                                  descrfct=descrfct_pycpp,
                                                  checkfct=checkfct_pycpp,
                                                  flagfct=lambda pkg,subdir:['-DPYMODNAME=%s'%subdir[6:]]))]
    l += [('app_.+', tfb.create_tfactory_binary(instsubdir='bin',namefct=namefct_app,
                                                  descrfct=descrfct_app))]
    l += [('libsrc', tfb.create_tfactory_binary(pkglib=True,namefct=namefct_lib,descrfct=descrfct_lib))]
    l += [('libinc',  tfh.tfactory_headerdeps)]#just for header dependencies


    return l

def ignore_file(f):
    f = f.name if hasattr(f,'name') else f
    return f[0]=='.' or '~' in f or '#' in f or f.endswith('.orig') or f.endswith('.bak') or f=='__pycache__'

def target_factories():
    #non-pattern factories:
    from . import tfact_prepinc
    from . import tfact_pyinit
    from . import tfact_reflogs
    from . import tfact_libavail
    l = []
    l += [tfact_prepinc.tfactory_prepinc]
    l += [tfact_pyinit.tfactory_pyinit]
    l += [tfact_reflogs.tfactory_reflogs]
    l += [tfact_libavail.tfactory_libavail]
    return l

def deinstall_parts(instdir,pkgname,current_parts,disappeared_parts):
    from . import dirs
    i=instdir
    if not ( i / '.sbinstalldir' ).exists():
        return
    unused=set()
    pydone=False
    pkgcache=dirs.pkg_cache_dir(pkgname)
    import shutil
    def rm_tree(p):
        shutil.rmtree( p, ignore_errors=True)
    def rm_file( p ):
        p.unlink(missing_ok = True)
    def rm_pattern(thedir,pattern):
        for f in thedir.glob(pattern):
            rm_file(f)

    for d in disappeared_parts:
        if d=='libinc':
            rm_tree( i / 'include' / pkgname)
        elif d=='libsrc':
            rm_pattern(i/'lib','*PKG__%s.*'%pkgname)
        elif d.startswith('app_'):
            _runnable_name='%s%s_%s' %( runnable_prefix,
                                        pkgname.lower(),
                                        d[4:].lower() )
            rm_tree( i / 'bin' / _runnable_name )
        elif d=='symlink__scripts':
            #FIXME: Next line clashes (see FIXME above)
            rm_pattern( i/'scripts',
                        '%s%s_*'%(runnable_prefix,pkgname.lower()) )
            (pkgcache/'symlinks'/'scripts.pkl').touch()
            rm_file(pkgcache/'symlinks'/'scripts.pkl.old')
        elif d=='symlink__data':
            rm_tree( i / 'data' / pkgname )
            ( pkgcache / 'symlinks' / 'data.pkl' ).touch()
            rm_file( pkgcache / 'symlinks' / 'data.pkl.old' )
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
                ( pkgcache / 'symlinks' / 'python.pkl' ).touch()
                rm_file( pkgcache / 'symlinks' / 'python.pkl.old' )
        elif d.startswith('pycpp_') or d=='symlink__python':
            if d.startswith('pycpp'):
                rm_file( ( i / 'python' / pkgname / '%s.so' )%d[6:] )
            if not pydone:
                pydone=True
                if not any((e.startswith('pycpp') or e=='symlink__python') for e in current_parts):
                    rm_tree( i / 'python' / pkgname )
                ( pkgcache / 'symlinks' / 'python.pkl' ).touch()
                rm_file( pkgcache / 'symlinks' / 'python.pkl.old' )
                ( pkgcache / 'pyinit' / 'pyinit.pkl' ).touch()
                #rm_file( pkgcache / 'pyinit' / 'pyinit.pkl.old' )
        else:
            unused.add(d)
    assert not unused,str(unused)
