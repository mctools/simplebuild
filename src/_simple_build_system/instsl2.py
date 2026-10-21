def _load( fn ):
    #Returns set of (destdir,linkname,src), or None if fn is absent or broken:
    from . import utils
    data = utils.pkl_load_or_none( fn )
    return data if isinstance( data, set ) else None

def main():
    import sys
    from . import utils
    fn=sys.argv[1]
    verbose=int(sys.argv[2]) if len(sys.argv)>=3 else 0
    #verbose flag: -1 quiet, 0 normal, 1 verbose.
    utils.install_symlinks_from_pickle( fn, _load, verbose > 0 )

if __name__=='__main__':
    import sys
    try:
        main()
    except KeyboardInterrupt:
        from .io import print
        print("<<symlink installation interrupted by user!>>>")
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)
