# Interactive review and updating of the reference logs of tests ("sb
# --reflogupdate"). This module contains the logic, independently of the user
# interface (see reflogui.py).

import os
import pathlib

def _random_code( n = 5 ):
    import random
    import string
    chars = string.ascii_lowercase + string.digits
    return ''.join( random.choice( chars ) for _ in range(n) )

class Candidate:

    """A test whose output differs from its reference log."""

    def __init__( self, name, pkgname, testdir, installed_reflog ):
        self.name = name
        self.pkgname = pkgname
        self.output = pathlib.Path(testdir) / name / 'output.log'
        self.installed_reflog = pathlib.Path(installed_reflog)
        self.updated = False
        self.job_failed = False#set if the test failed when rerun
        self._lines = None

    def lines( self ):
        """Returns (reflog_lines,output_lines), or None if not readable."""
        if self._lines is None:
            from .reflogdiff import read_lines
            try:
                self._lines = ( read_lines( self.installed_reflog ),
                                read_lines( self.output ) )
            except OSError:
                return None
        return self._lines

    def forget_lines( self ):
        self._lines = None

    @property
    def identical( self ):
        ll = self.lines()
        return ll is not None and ll[0] == ll[1]

    def source_reflog( self ):
        """The reference log in the package. Returns (path_to_show,
        path_to_write), where the latter has all symlinks resolved (the
        reference log in the package might itself be a symlink)."""
        #The installed reference log is a symlink to the file in the package,
        #via the symlink to the package in the build directory (e.g.
        #<blddir>/pkgs/<pkgname>/scripts/<scriptname>.log):
        target = pathlib.Path( os.readlink( self.installed_reflog ) )
        pkglink = target.parent.parent
        shown = pathlib.Path( os.path.realpath( pkglink ) ) / target.parent.name / target.name
        return shown, pathlib.Path( os.path.realpath( shown ) )

class Session:

    """State of an interactive session. To avoid accidental updates of
    reference logs, each update requires a randomly generated code to be typed
    in reverse order, unless this requirement was disabled for the rest of the
    session (which itself requires a code to be typed)."""

    def __init__( self, testdir, installdir, filters = None,
                  rerun_fct = None, rebuild_fct = None ):
        from .testlauncher import load_results, make_filter_fct
        self.testdir = pathlib.Path(testdir)
        self.installdir = pathlib.Path(installdir)
        self.rerun_fct = rerun_fct
        self.rebuild_fct = rebuild_fct
        self.code_required = True
        self.updated_files = []
        self.candidates = []
        self.nfailed_jobs = 0
        self.runinfo, results = load_results( testdir )
        if self.runinfo is None:
            return
        filter_fct = make_filter_fct( filters )
        for r in results:
            if not r.has_reflog or not filter_fct( r.name ):
                continue
            if r.ec != 0:
                self.nfailed_jobs += 1
                continue
            c = Candidate( r.name, r.pkgname, testdir,
                           self.installdir / 'tests' / 'testref' / f'{r.name}.log' )
            if c.lines() is not None and not c.identical:
                self.candidates.append( c )

    @property
    def has_results( self ):
        return self.runinfo is not None

    def new_code( self ):
        return _random_code()

    @staticmethod
    def code_matches( code, typed ):
        return ( typed or '' ).strip().lower() == code[::-1]

    def disable_code_requirement( self ):
        self.code_required = False

    def update( self, candidate ):
        """Replace the reference log in the package with the output of the
        test. Returns the path to the updated file (as shown to users)."""
        from .utils import write_atomic
        assert not candidate.job_failed
        shown, target = candidate.source_reflog()
        data = candidate.output.read_bytes()
        try:
            mode = target.stat().st_mode & 0o7777
        except OSError:
            mode = None
        write_atomic( target, data, mode = mode )
        candidate.updated = True
        candidate.forget_lines()
        #Also update the comparison in the test results, so reports show that
        #the output now matches the reference log:
        from .reflogdiff import compare_and_write_diff
        td = self.testdir / candidate.name
        same = compare_and_write_diff( candidate.installed_reflog, candidate.output,
                                       td / 'refdiff.log' )
        write_atomic( td / 'ecdiff.txt', '0\n' if same else '1\n' )
        if shown not in self.updated_files:
            self.updated_files.append( shown )
        return shown

    def rerun( self, candidate, rebuild = False ):
        """Run the test again (optionally after rebuilding). Returns (ok,msg)."""
        if rebuild:
            ok = self.rebuild_fct() if self.rebuild_fct else False
            if not ok:
                return False, 'Build failed'
        ec = self.rerun_fct( candidate.name ) if self.rerun_fct else None
        candidate.forget_lines()
        candidate.updated = False
        if ec is None:
            return False, 'Could not run the test'
        candidate.job_failed = ( ec != 0 )
        if candidate.job_failed:
            return False, f'The test failed (exit code {ec})'
        if candidate.lines() is None:
            return False, 'Could not read the output of the test'
        if candidate.identical:
            return True, 'The output is now identical to the reference log'
        return True, 'The output still differs from the reference log'
