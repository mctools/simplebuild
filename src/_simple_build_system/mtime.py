import os
import pathlib
from . import conf

_islink=os.path.islink
_osstat=os.stat
def mtime(f):
    s = f.stat() if hasattr(f,'stat') else _osstat(f)
    return max(s.st_mtime,s.st_ctime)
    #m=max(s.st_mtime,s.st_ctime)
    #if not _islink(f):
    #    return m
    #s=os.lstat(f)
    #return max(m,s.st_mtime,s.st_ctime)

def mtime_pathlist(files_and_dirs,depth=0):
    """common (highest) modification time of input files and directories. Directories are searched recursively."""
    join  = os.path.join
    isdir = os.path.isdir
    exists = os.path.exists
    ld = os.listdir
    mt = float('-inf')
    moredirs=[]
    for fd in files_and_dirs:
        if not exists(fd):
            raise RuntimeError('Indicated path does not exist: %s'%fd)
        mt = max(mt,mtime(fd))
        if isdir(fd):
            for f in ld(fd):
                f = join(fd,f)
                if isdir(f):
                    moredirs+=[f]
                else:
                    mt = max(mt,mtime(f))
    if moredirs:
        if depth>20:
            raise RuntimeError('Max recursion depth exceeded in mtime_pathlist')
        mt = max(mt,mtime_pathlist(moredirs,depth+1))
    return mt

def mtime_pkg(pkg):
    #assuming the vast majority of files to be in proper subdirs, we simply take
    #the highest mtime of the package cfg file and any file in any subdir. To detect
    #subdirs disappearing we also take the mtime of the pkg dir itself and the first level of subdirs.
    join  = os.path.join
    isdir = os.path.isdir
    ld = os.listdir
    d=pkg.dirname
    #ctime for metadata, mtime for content
    f=join(d,conf.package_cfg_file)
    mt=max(mtime(f),mtime(d))
    for fd in ld(d):
        if conf.ignore_file(fd):
            continue
        fd=join(d,fd)
        if isdir(fd):
            mt = max(mt,mtime(fd))
            for f in ld(fd):
                if conf.ignore_file(f):
                    continue
                f = join(fd,f)
                mt = max(mt,mtime(f))
    return mt

def mtime_cmake():
    from . import dirs
    ll = [dirs.cmakedetectdir] + list(dirs.extraextdeppath)
    files  = []
    for ddir in ll:
        files += list(ddir.glob('**/*.txt'))
        files += list(ddir.glob('**/*.cmake'))
        files += list(ddir.glob('**/*.py'))
    files = [ f for f in files if '#' not in f.name ]
    mt=-1
    for f in files:
        mt=max(mt,mtime(f))
    return mt

def mtime_pymods():
    files = [ str(e) for e in pathlib.Path(__file__).parent.glob('*.py') ]

    files = [ f for f in files if '#' not in f ]
    mt=-1
    for f in files:
        mt=max(mt,mtime(f))
    return mt
