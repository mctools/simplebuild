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

def pkl_load(fn_or_fh):
    import pickle
    if hasattr(fn_or_fh,'read'):
        #argument is filehandle:
        return pickle.load(fn_or_fh)#filehandle already
    else:
        #argument is filename:
        with pathlib.Path(fn_or_fh).open('rb') as fh:
            d=pickle.load(fh)
        return d

def pkl_dump(data,fn_or_fh):
    import pickle
    if hasattr(fn_or_fh,'write'):
        #argument is filehandle:
        d=pickle.dump(data,fn_or_fh)
        fn_or_fh.flush()
        return d
    else:
        #argument is filename:
        with pathlib.Path(fn_or_fh).open('wb') as fh:
            d=pickle.dump(data,fh)
        return d

def update_pkl_if_changed(pklcont,filename):
    old = os.path.exists(filename)
    readold = False
    oldcont = None
    changed = True
    if old:
        try:
            oldcont=pkl_load(filename)
            readold = True
        except EOFError:
            from . import io as _io
            _io.print( "WARNING: Old pickle file %s ended unexpectedly"%filename)
            oldcont = None
            readold = False
        if readold and oldcont == pklcont:
            changed = False
    if not changed:
        return oldcont
    if old:
        os.rename(filename,str(filename)+'.old')
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
    #Path.is_relative_to(..) was introduced in Python 3.9, this function lets us
    #support python 3.8.
    assert isinstance( p, pathlib.Path )
    if hasattr(p,'is_relative_to'):
        #Python 3.9+:
        return p.is_relative_to(pother)
    else:
        #Python 3.8:
        try:
            p.relative_to(pother)
            return True
        except ValueError:
            return False

def _remove_symlinks( symlinks, verbose ):
    #FIXME: pathlib
    dirs_with_removals=set()#to test for empty dirs to be removed at the end
    if verbose:
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


def update_symlinks( oldlist, newlist, verbose ):
    if verbose:
        from .io import print
    else:
        def print( *a, **kw ):
            return None

    obsoleted = oldlist.difference(newlist)
    _remove_symlinks( [ os.path.join(destdir,linkname)
                        for destdir,linkname,src in obsoleted ],
                      verbose )
    #create dirs:
    for dd in set(d for d,_,_ in newlist):
        mkdir_p(dd)
    #create links:
    for destdir,linkname,src in newlist:
        fn = os.path.join( destdir, linkname )
        if os.path.lexists(fn):
            if os.path.samefile( fn, src ):
                #Already in place
                continue
            else:
                try:
                    os.unlink(fn)
                except FileNotFoundError:
                    #Removed in race condition?
                    pass
        print("Installing symlink %s"%fn)
        try:
            os.symlink(src,fn)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                pass#could have been created previously before an abort
            else:
                raise
