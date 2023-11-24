import os
import errno
import sys
import pathlib
from . import utils
from .io import print

def go():
    fn=sys.argv[1]
    verbose=int(sys.argv[2]) if len(sys.argv)>=3 else 0
    files,srcdir,destdir = utils.pkl_load(fn)
    ofn='%s.old'%fn
    try:
        oldfiles,_,_ =  utils.pkl_load(ofn) if os.path.exists(ofn) else (None,None,None)
    except EOFError:
        print("ERROR: Old pickle file %s ended unexpectedly."%ofn)
        raise
    join=os.path.join

    #first remove any now obsolete links in the destination directory:
    if oldfiles:
        current = set(t for s,t in oldfiles)
        needed = set(t for s,t in files)
        obsoleted = current.difference(needed)
        for f in obsoleted:
            if verbose>0:
                print(("Removing obsolete symlink",f))
            try:
                os.remove(join(destdir,f))
            except OSError as exc:
                if exc.errno == errno.ENOENT and not os.path.exists(join(destdir,f)):
                    #perhaps we were aborted and restarted so we should just report and carry on
                    if verbose>=0:
                        print("WARNING: Obsolete symlink already removed.")
                    pass
                else:
                    raise
        if not needed:
            #we removed all of our files, remove dir if not empty:
            if not any(pathlib.Path(destdir).iterdir()):
                try:
                    os.rmdir(destdir)
                except OSError as exc:
                    if exc.errno == errno.ENOENT:
                        pass#could have been already been removed by other target due to race condition
                    else:
                        raise
        current=current.intersection(needed)
    else:
        current=set()

    if len(files)>len(current):
        if not os.path.isdir(destdir):
            utils.mkdir_p(destdir)
        for s,t in files:
            if t not in current:
                if verbose>0:
                    print("Installing symlink %s"%join(destdir,t))
                try:
                    os.symlink(join(srcdir,s),join(destdir,t))
                except OSError as exc:
                    if exc.errno == errno.EEXIST:
                        pass#could have been created previously before an abort
                    else:
                        raise

try:
    go()
except KeyboardInterrupt:
    print("<<symlink installation interrupted by user!>>>")
    #Fixme: Any way to recover state?? (if so we should also catch other errors)
    sys.stdout.flush()
    sys.stderr.flush()
    import time
    time.sleep(0.2)
    sys.exit(1)

sys.exit(0)
