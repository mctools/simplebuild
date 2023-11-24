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
    old=os.path.exists(filename)
    changed = True
    if old:
        try:
            oldcont=pkl_load(filename)
        except EOFError:
            from . import io as _io
            _io.print( "WARNING: Old pickle file %s ended unexpectedly"%filename)
            oldcont=(None,'bad....')
            pass
        if oldcont==pklcont:
            changed=False
    if old and changed:
        os.rename(filename,str(filename)+'.old')
    if changed:
        pkl_dump(pklcont,filename)

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
