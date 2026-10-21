import os
import errno
import sys
import pathlib

def err(msg):
    #fixme: remove this functions from utils
    from .error import error as errfct
    errfct( msg )

def system(cmd,*,env=None):
    #flush output, to avoid confusing ordering in log-files:
    sys.stdout.flush()
    sys.stderr.flush()
    #rather than os.system, we call "bash -c <cmd>" explicitly through
    #the subprocess module, making sure we can always use bash syntax:
    import subprocess
    cmd=['bash','-c',cmd]
    try:
        ec=subprocess.call(cmd,env=env)
    except KeyboardInterrupt:
        sys.stdout.flush()
        sys.stderr.flush()
        import time
        time.sleep(0.2)
        from . import io as _io
        _io.print("<<<Command execution interrupted by user!>>>")
        if hasattr(sys,'exc_clear'):
            sys.exc_clear()#python2 only
        ec=126
    #wrap exit code to 0..127, in case the return code is passed on to sys.exit(ec).
    sys.stdout.flush()
    sys.stderr.flush()
    if ec>=0 and ec<=127:
        return ec
    return 127


def run(cmd):
    sys.stdout.flush()
    sys.stderr.flush()
    if not isinstance(cmd,list):
        cmd=cmd.split()
    import subprocess
    output=None
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.communicate()[0]
        ec = p.returncode
    except (OSError,subprocess.SubprocessError):
        ec = 1
    return (ec,output if ec==0 else '')

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def rm_f(path):
    try:
        os.remove(path)#only succeeds if path exists and is not a directory
    except OSError as e:
        if e.errno == errno.ENOENT:#no such file or directory
            return#not an error, rm -f should exit silently here
        raise

def rm_rf(path):
    #First attempt with os.remove, and only in case it was a directory go for
    #shutil.rmtree (since shutil.rmtree prints error messages if fed symlinks to
    #directories):
    import shutil
    try:
        os.remove(path)
    except OSError as e:
        if e.errno == errno.ENOENT:#no such file or directory
            return#not an error, rm -rf should exit silently here
        elif e.errno != errno.EISDIR and e.errno!=errno.EPERM:
            raise
    #is apparently a directory
    try:
        shutil.rmtree(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return#Sudden disappearance is still ok.
        raise

def is_empty_dir( path ):
    #any(..) returns False for empty iterables.
    return path.is_dir() and not any( path.iterdir() )

def rmdir(path):
    p = pathlib.Path(path)
    if p.is_dir() and not any(p.iterdir()):
        p.rmdir()

def listfiles(d,filterfnc=0,error_on_no_match=True,ignore_logs=False):
    from . import conf
    for f in os.listdir(d):
        if ignore_logs and f.endswith('.log'):
            continue
        if not conf.ignore_file(f) and not os.path.isdir(os.path.join(d,f)):
            if filterfnc:
                if filterfnc(f):
                    yield f
                elif error_on_no_match:
                    from . import error
                    error.error("Forbidden file %s/%s"%(d,f))
            else:
                yield f

def is_executable(fn):
    return os.access(fn,os.X_OK)

def write_atomic( path, data, *, mode = None ):
    """Write data (str or bytes) to the file atomically, i.e. a crash or
    interruption will never leave behind a partially written file. This is
    done by writing to a temporary file in the same directory, which is then
    moved into place. If mode is given, the file permissions are set to it."""
    path = pathlib.Path(path)
    tmp = path.parent / f'.{path.name}.tmp{os.getpid()}'
    try:
        with tmp.open( 'wb' if isinstance(data,bytes) else 'wt' ) as fh:
            fh.write( data )
        if mode is not None:
            os.chmod( tmp, mode )
        os.replace( tmp, path )
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise

def pkl_load(fn_or_fh):
    import pickle
    if hasattr(fn_or_fh,'read'):
        #argument is filehandle:
        return pickle.load(fn_or_fh)#filehandle already
    else:
        #argument is filename:
        with pathlib.Path(fn_or_fh).open('rb') as fh:
            return pickle.load(fh)

def pkl_load_or_none( fn, *, warn_if_broken = True ):
    """Load the pickle file if it exists and can be loaded, otherwise return
    None. A broken file (e.g. truncated or from an incompatible version) gives a
    warning (unless warn_if_broken is False), and is removed."""
    fn = pathlib.Path(fn)
    try:
        return pkl_load( fn )
    except FileNotFoundError:
        return None
    except Exception as e:
        if warn_if_broken:
            from .io import print
            print(f'WARNING: Ignoring broken file {fn} ({e.__class__.__name__})')
        try:
            fn.unlink()
        except OSError:
            pass
        return None

def pkl_dump(data,fn_or_fh):
    import pickle
    if hasattr(fn_or_fh,'write'):
        #argument is filehandle:
        d=pickle.dump(data,fn_or_fh)
        fn_or_fh.flush()
        return d
    else:
        #argument is filename (write atomically):
        write_atomic( fn_or_fh, pickle.dumps(data) )

def update_pkl_if_changed(pklcont,filename):
    """Write the pickle file if the content changed (to avoid triggering
    makefile targets unnecessarily). The previous file is kept with an extra
    .old suffix. Returns the previous content (None if absent or broken)."""
    filename = pathlib.Path(filename)
    oldcont = pkl_load_or_none( filename )
    if oldcont is not None and oldcont == pklcont:
        return oldcont
    if oldcont is not None:
        os.replace( filename, str(filename)+'.old' )
    pkl_dump(pklcont,filename)
    return oldcont

def shlex_split(s):
    try:
        import shlex
    except ImportError:
        shlex=None
    if shlex:
        return shlex.split(s)
    else:
        return s.split()#hope user didnt use spaces in directories

class rpath_appender:
    def __init__( self, lang, shlib ):
        from . import env
        langinfo=env.env['system']['langs'][lang]
        rpath_pattern = langinfo['rpath_flag_lib' if shlib else 'rpath_flag_exe']
        self.__patterns = [ rpath_pattern ]
        if langinfo['can_use_rpathlink_flag'] and '-rpath' in rpath_pattern and '-rpath-link' not in rpath_pattern:
            self.__patterns += [ self.__patterns[0].replace('-rpath','-rpath-link') ]
    def apply_to_dir( self, directory ):
        return [ p%directory for p in self.__patterns ]
    def apply_to_flags( self, flag_list ):
        found_dirs = []
        for f in flag_list:
            for p in ['-L','-Wl,rpath,','-Wl,rpath=','-Wl,rpath-link,','-Wl,rpath-link=']:
                _ = None
                if f.startswith(p):
                    _ = f[len(p):]
                    if not _:
                        continue
                elif not f.startswith('-'):
                    _ = pathlib.Path(f)
                    if _.exists() and not _.is_dir() and _.parent.is_dir():
                        _ = str(_.parent.absolute().resolve())#../bla/libfoo.so -> /some/where/bla
                    elif not _.exists():
                        _ = None
                _ = str(_) if _ else None
                if _ and _ not in found_dirs:
                    found_dirs.append( _ )
        res = flag_list[:]
        for d in found_dirs:
            res += self.apply_to_dir( d )
        return res

def path_is_relative_to( p, pother ):
    assert isinstance( p, pathlib.Path )
    return p.is_relative_to(pother)

def _remove_symlinks( symlinks, do_print ):
    #FIXME: pathlib
    dirs_with_removals=set()#to test for empty dirs to be removed at the end
    if do_print:
        from .io import print
    else:
        def print( *a, **kw ):
            return None
    for fn in symlinks:
        print("Removing obsolete symlink %s"%fn)
        try:
            os.remove(fn)
        except OSError as exc:
            if exc.errno == errno.ENOENT and not os.path.exists(fn):
                #perhaps we were aborted and restarted so we should just report and carry on
                print("WARNING: Obsolete symlink already removed: %s"%fn)
                pass
            else:
                raise
        dirs_with_removals.add( os.path.dirname( fn ) )

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

def update_symlinks( oldlist, newlist, do_print ):
    """Install the symlinks in newlist and remove those in oldlist which are not
    also in newlist. Each list is a set of (destdir,linkname,src) tuples."""
    if do_print:
        from .io import print
    else:
        def print( *a, **kw ):
            return None

    obsoleted = oldlist.difference(newlist)
    _remove_symlinks( [ os.path.join(destdir,linkname)
                        for destdir,linkname,src in obsoleted ],
                      do_print )
    #create dirs:
    for dd in set(d for d,_,_ in newlist):
        mkdir_p(dd)
    #create links:
    for destdir,linkname,src in newlist:
        fn = os.path.join( destdir, linkname )
        if os.path.islink(fn):
            if os.readlink(fn) == str(src):
                continue#Already in place
            #Wrong or dangling link (e.g. pointing to a moved file):
            try:
                os.unlink(fn)
            except FileNotFoundError:
                pass#Removed in race condition?
        elif os.path.isdir(fn):
            from .error import error
            error(f'Directory found where a symlink should be installed: {fn}')
        elif os.path.lexists(fn):
            os.unlink(fn)#Regular file in the way
        print("Installing symlink %s"%fn)
        try:
            os.symlink(src,fn)
        except FileExistsError:
            #Created in race condition?
            if os.readlink(fn) != str(src):
                raise

def install_symlinks_from_pickle( pklfile, load_fct, do_print ):
    """Used by the instsl and instsl2 modules invoked from the generated
    makefiles. The pickle file holds the needed links, and load_fct(filename)
    must load it into a set of (destdir,linkname,src) tuples (or return None if
    the file is absent or broken). Links previously installed (recorded in a
    file with the .installed suffix after each successful installation) or
    needed (recorded in a file with the .old suffix by update_pkl_if_changed),
    which are not needed any longer, are removed."""
    pklfile = pathlib.Path(pklfile)
    needed = load_fct( pklfile )
    if needed is None:
        from .error import error
        error(f'Could not load {pklfile} (try to run "sb -i")')
    installed_file = pklfile.parent / ( pklfile.name + '.installed' )
    previous = set()
    for f in ( installed_file, pklfile.parent / ( pklfile.name + '.old' ) ):
        _ = load_fct( f )
        if _ is not None:
            previous.update( _ )
    update_symlinks( previous, needed, do_print )
    pkl_dump( needed, installed_file )
