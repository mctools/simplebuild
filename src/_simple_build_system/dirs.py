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

#Increase whenever the layout of the build or install directories changes in
#an incompatible manner (triggering complete rebuilds of existing caches):
cache_layout_version = '3'

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

#Named targets (i.e. targets which are not files) in the makefiles are
#represented by empty files in a separate directory for each package, so that
#all the files of a package can be removed together. Such targets are named
#either "<pkgname>" (the target for the entire package) or
#"<pkgname>__<subname>" (package names never contain "__"). Global targets are
#named "_global__<subname>" (package names never start with "_"):
named_targets_dir = blddir / 'named_targets'
_named_target_pkgdone = '.pkgdone'

def named_target_subdir( targetname ):
    """The name of the subdirectory of named_targets_dir holding the file for
    the named target."""
    return targetname.partition('__')[0]

def named_targets_pkg_dir(pkg):
    return named_targets_dir / _pkgname(pkg)

def makefile_named_target( targetname ):
    assert '/' not in targetname
    d, sep, subname = targetname.partition('__')
    assert d and ( subname if sep else '__' not in targetname )
    return '${TRG}/%s/%s'%( d, subname if sep else _named_target_pkgdone )

#Characters which would break the generated makefiles and shell commands, in
#which the build and install directories are used unquoted:
_unsafe_chars_blddir = set( '$#:;%\'"\\`*?[](){}|&<>!' )

def check_path( path, descr, unsafe_chars = None ):
    """Check that a directory path can be used, with a clear error message if
    not."""
    p = str(path)
    bad = sorted( c for c in set(p)
                  if c.isspace() or ( unsafe_chars and c in unsafe_chars ) )
    if bad:
        from . import error
        _ = ' '.join( repr(c) for c in bad )
        error.error(f'The {descr} path contains unsupported characters ({_}),'
                    f' please use a different location: {p}')
    if len(p) <= 3:
        from . import error
        error.error(f'Suspiciously short {descr} path: {p}')

check_path( blddir, 'build directory', _unsafe_chars_blddir )
check_path( installdir, 'install directory', _unsafe_chars_blddir )
for _ in pkgsearchpath:
    check_path( _, 'package search' )

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
