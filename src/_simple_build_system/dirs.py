#global variables
import pathlib
import os
from . import conf#project specific configuration

#system dir is one up from the modules dir:
sysdir = str(pathlib.Path(__file__).resolve().absolute().parent.parent)
blddir = conf.build_dir() # imports envcfg
makefiledir = blddir / 'makefiles'

extrapkgpath = conf.extra_pkg_path() # imports envcfg
pkgsearchpath = conf.pkg_search_path() # imports envcfg
extraextdeppath = conf.extra_extdep_path() # imports envcfg

installdir = conf.install_dir() # imports envcfg
testdir = conf.test_dir() # imports envcfg
main_bundle_pkg_root = conf.main_bundle_pkg_root() # imports envcfg
datadir = pathlib.Path(__file__).resolve().absolute().parent / 'data'
cmakedetectdir = datadir / 'cmake'

incdirname='include'
#libdirname='lib'#fixme: unused, 'lib' is simply hardcoded in a few places.

envcache = blddir / 'env.cache'
systimestamp_cache=blddir / 'systimestamp.cache'
lockfile=blddir / ".lock"

def makefile_instdir(*subpaths):
    if not subpaths:
        return "${INST}"
    subpaths=os.path.join(*subpaths)
    if subpaths[0]=='/':
        subpaths=os.path.relpath(subpaths,installdir)
    return os.path.join("${INST}",subpaths)

def makefile_blddir(*subpaths):
    if not subpaths:
        return "${BLD}"
    subpaths=os.path.join(*subpaths)
    if subpaths[0]=='/':
        subpaths=os.path.relpath(subpaths,blddir)
    return os.path.join("${BLD}",subpaths)

def _pkgname(pkg):
    return pkg.name if hasattr(pkg,'name') else pkg

def pkg_cache_dir(pkg,*subpaths):
    return blddir.joinpath('pc',_pkgname(pkg),*subpaths)

def makefile_pkg_cache_dir(pkg,*subpaths):
    return os.path.join('${BLD}','pc',_pkgname(pkg),*subpaths)

#where we link (or create dynamic pkgs):
pkgdirbase = blddir / 'pkgs'
def pkg_dir(pkg,*subpaths):
    return pkgdirbase.joinpath( _pkgname(pkg),*subpaths )

def makefile_pkg_dir(pkg,*subpaths):
    return os.path.join('${PKG}',_pkgname(pkg),*subpaths)

#sanity:
for d in [str(x) for x in [blddir, *pkgsearchpath, installdir]]:
    assert ' ' not in d, 'Spaces not allowed in directory names. Illegal path is: "%s"'%d
    assert len(d)>3,f"suspiciously short path name: {d}"

def create_bld_dir():
    fingerprint = blddir  / '.sbbuilddir'
    if  blddir.exists() and not fingerprint.exists():
        from . import error
        error.error(f'Did not find expected fingerprint file at: {fingerprint}')
    blddir.mkdir(parents=True,exist_ok=True)
    fingerprint.touch()
    assert blddir.is_dir()
    assert ( blddir  / '.sbbuilddir' ).exists()

def create_install_dir():
    fingerprint = installdir  / '.sbinstalldir'
    if  installdir.exists() and not fingerprint.exists():
        from . import error
        error.error(f'Did not find expected fingerprint file at: {fingerprint}')
    installdir.mkdir(parents=True,exist_ok=True)
    fingerprint.touch()
    assert installdir.is_dir()
    assert ( installdir  / '.sbinstalldir' ).exists()
