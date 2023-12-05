def main():
    import sys
    import errno
    from . import utils
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
    utils.update_symlinks( current, needed, verbose )

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
