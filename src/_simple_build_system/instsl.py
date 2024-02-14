def extract_filelist( fn ):
    from . import utils
    import os
    try:
        files,srcdir,destdir = utils.pkl_load(fn)
    except EOFError:
        print("ERROR: pickle file %s ended unexpectedly."%fn)
        raise
    return set( (destdir, fnlink, os.path.join( srcdir, fnsrc ) )
                for fnsrc, fnlink in files )
def main():
    from . import utils
    import sys
    import os
    fn=sys.argv[1]
    verbose=int(sys.argv[2]) if len(sys.argv)>=3 else 0
    #verbose flag: -1 quiet, 0 normal, 1 verbose.
    do_print = verbose > 0
    newlist = extract_filelist( fn )
    oldfn = '%s.old'%fn
    oldlist = extract_filelist( oldfn ) if os.path.exists(oldfn) else set()
    utils.update_symlinks( oldlist, newlist, do_print )

if __name__=='__main__':
    import sys
    try:
        main()
    except KeyboardInterrupt:
        from .io import print
        print("<<symlink installation interrupted by user!>>>")
        #Fixme: Any way to recover state?? (if so we should also catch other errors)
        sys.stdout.flush()
        sys.stderr.flush()
        import time
        time.sleep(0.2)
        sys.exit(1)
