import os
import errno
import sys
import subprocess
import shutil
import contextlib
import tempfile
import atexit

__all__ = [ 'quote', 'mkdir_p', 'chmod_x', 'rm_rf', 'rm_f', 'isemptydir',
            'system','system_throw', 'which', 'quote_cmd', 'recursive_find',
            'remove_atexit' ]

#NB: This module is still being imported by python2 in a few unit tests!!!

try:
    #Python3: quote from shlex + make pathlib-aware:
    from shlex import quote as _shlex_quote
    def quote(s):
        return _shlex_quote(str(s) if hasattr(s,'__fspath__') else s)
except ImportError:
    #Python2: quote from pipes:
    from pipes import quote

def mkdir_p(path,*args):
    """python equivalent of 'mkdir -p ...'"""
    if args:
        mkdir_p(path)
        for a in args:
            mkdir_p(a)
        return
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def chmod_x(path):
    """python equivalent of 'chmod +x ...'"""
    os.chmod(path, os.stat(path).st_mode | 0o111)

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

def isemptydir(path):
    try:
       for f in os.listdir(path):
           return False
    except OSError as e:
        if e.errno == errno.ENOENT:#no such file or directory
            return False
        if e.errno == errno.ENOTDIR:#not a directory
            return False
        raise
    return True

def which(cmd):
    """Function like BASH which (returns None if cmd not found)"""
    try:
        import shutil
    except ImportError:
        shutil = None
    if shutil and hasattr(shutil,'which'):
        cmd = shutil.which(cmd)
    else:
        from distutils.spawn import find_executable
        cmd=find_executable(cmd)
    if not cmd:
        return None
    return os.path.abspath(os.path.realpath(cmd))

def quote_cmd(cmd):
    if isinstance(cmd,list):
        return ' '.join(quote(c) for c in cmd)
    return cmd

def system(cmd,catch_output=False,env=None):
    """A better alternative to os.system which flushes stdout/stderr, makes sure
       the shell is always bash, and wraps exit codes larger than 127 to
       127. Set catch_output to True to instead return both exit code and the
       output of the command in a string.

    """
    #flush output, to avoid confusing ordering in log-files:
    sys.stdout.flush()
    sys.stderr.flush()
    #rather than os.system, we call "bash -c <cmd>" explicitly through
    #the subprocess module, making sure we can always use bash syntax:
    cmd=['bash','-c',cmd]
    #wrap exit code to 0..127, in case the return code is passed on to
    #sys.exit(ec):
    def fixec(ec):
        return ec if (ec>=0 and ec<=127) else 127
    if catch_output:
        try:
            p = subprocess.Popen(cmd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,env=env)
            output = p.communicate()[0]
        except subprocess.CalledProcessError:
            #todo: in case of failure we should return the output as well!
            return 1,''
        return fixec(p.returncode),output
    else:
        ec=subprocess.call(cmd,env=env)
    sys.stdout.flush()
    sys.stderr.flush()
    return fixec(ec)

def system_throw(cmd,catch_output=False,env=None):
    """same as system except doesn't return exit code and throws RuntimeError in
    case of non-zero exit code"""
    out=None
    if catch_output:
        ec,out = system(cmd,catch_output,env=env)
    else:
        ec = system(cmd,catch_output,env=env)
    if ec:
        raise RuntimeError('command failed: %s'%cmd)
    return out

def recursive_find(searchdir,filenamepattern):
    import os
    import fnmatch
    # matches=set()
    for root, dirnames, filenames in os.walk(searchdir):
        for filename in fnmatch.filter(filenames+dirnames, filenamepattern):
            yield os.path.join(root, filename)

_files_to_clean = set()
def remove_atexit(*filelist):
    global _files_to_clean
    for f in filelist:
        _files_to_clean.add(os.path.abspath(os.path.realpath(f)))

def _filecleaner():
    global _files_to_clean
    for f in _files_to_clean:
        rm_rf(f)
atexit.register(_filecleaner)

def exec_bash_and_updateenv(cmd):
    """Execute a given bash command and update environment variables in current
    python process accordingly

    """
    import os
    import sys
    import subprocess
    import shlex
    import json
    #Execute with /usr/bin/env bash and use python3+json to stream the resulting
    #os.environ to stdout, using a well-defined encoding:
    import pathlib
    pyintrp = shlex.quote(str(pathlib.Path(sys.executable)))
    pycmd=( 'import os,sys,json;sys.stdout.buffer.write('
            'json.dumps(dict(os.environ)).encode("utf8"))')
    cmd=['/usr/bin/env','bash', '-c', '%s && %s -c %s'%(cmd,
                                                        pyintrp,
                                                        shlex.quote(pycmd))]
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    #Unpack the streamed os.environ, using the same encoding:
    env = json.loads(pipe.stdout.read().decode('utf8'))
    os.environ = env

def source_bash_file(fn):
    """Source a given bash file and update environment variables in current
    python process accordingly"""
    import pathlib
    import shlex
    exec_bash_and_updateenv('source %s'%shlex.quote(str(pathlib.Path(fn))))

@contextlib.contextmanager
def changedir(subdir):
    """Context manager for working in a given subdir and then switching back"""
    the_cwd = os.getcwd()
    os.chdir(subdir)
    try:
        yield
    finally:
        os.chdir(the_cwd)

@contextlib.contextmanager
def work_in_tmpdir():
    """Context manager for working in a temporary directory (automatically
    created+cleaned) and then switching back"""
    the_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            yield
    finally:
        os.chdir(the_cwd)
