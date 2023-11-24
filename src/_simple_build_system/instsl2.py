import os
import errno
import sys
import pathlib
from . import utils
from .io import print

def go():
    join=os.path.join

    fn=sys.argv[1]
    verbose=int(sys.argv[2]) if len(sys.argv)>=3 else 0
    needed=utils.pkl_load(fn)
    ofn='%s.old'%fn
    try:
        current = utils.pkl_load(ofn)
    except EOFError:
        current = set()
    except IOError as e:
        if e.errno == errno.ENOENT:#no such file or directory
            current = set()
        else:
            raise
    dirs_with_removals=set()#to test for empty dirs to be removed at the end
    if current:
        #Check for and remove any obsolete links:
        if True:
            #extra test for robustness that we really have all current here!
            for destdir,linkname,src in current:
                if not os.path.exists(join(destdir,linkname)):
                    #link missing, or broken.
                    if os.path.lexists(join(destdir,linkname)):
                        #link was actually existing, but broken
                        print("WARNING: Having to fix broken link: %s"%join(destdir,linkname))
                        os.remove(join(destdir,linkname))
                    else:
                        print("WARNING: Having to recreate supposedly preexisting link: %s"%join(destdir,linkname))
                    utils.mkdir_p(destdir)
                    os.symlink(src,join(destdir,linkname))

        obsoleted = current.difference(needed)
        for destdir,linkname,src in obsoleted:
            if verbose>0:
                print("Removing obsolete symlink %s %s"%(destdir,linkname))
            try:
                os.remove(join(destdir,linkname))
            except OSError as exc:
                if exc.errno == errno.ENOENT and not os.path.exists(join(destdir,linkname)):
                    #perhaps we were aborted and restarted so we should just report and carry on
                    if verbose>=0:
                        print("WARNING: Obsolete symlink already removed.")
                    pass
                else:
                    raise
            dirs_with_removals.add(destdir)
        needed=needed.difference(current)

    if needed:
        #create dirs:
        for dd in set(d for d,_,_ in needed):
            utils.mkdir_p(dd)
        #create links:
        for destdir,linkname,src in needed:
            if verbose>0:
                print("Installing symlink %s"%join(destdir,linkname))
            try:
                os.symlink(src,join(destdir,linkname))
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    pass#could have been created previously before an abort
                else:
                    raise

    #check for and cleanup empty dirs:
    if dirs_with_removals:
        #we removed files, remove dirs if not empty:
        def isemptydir( p ):
            return not any( pathlib.Path(p).iterdir() )
        for d in (d for d in dirs_with_removals if isemptydir(d)):
            try:
                os.rmdir(d)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    pass#could have been already been removed by other target due to race condition
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
