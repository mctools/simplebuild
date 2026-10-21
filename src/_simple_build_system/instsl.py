def extract_filelist( fn ):
    #Returns set of (destdir,linkname,src), or None if fn is absent or broken:
    from . import utils
    import os
    data = utils.pkl_load_or_none( fn )
    if data is None:
        return None
    if isinstance( data, set ):
        return data#.installed files store the extracted sets directly
    files,srcdir,destdir = data
    return set( (destdir, fnlink, os.path.join( srcdir, fnsrc ) )
                for fnsrc, fnlink in files )

def main():
    from . import utils
    import sys
    fn=sys.argv[1]
    verbose=int(sys.argv[2]) if len(sys.argv)>=3 else 0
    #verbose flag: -1 quiet, 0 normal, 1 verbose.
    utils.install_symlinks_from_pickle( fn, extract_filelist, verbose > 0 )

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
