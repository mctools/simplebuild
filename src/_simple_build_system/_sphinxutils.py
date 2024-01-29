
# Various utility functions to be used in the sphinx doc conf.py in both
# simplebuild itself, but also related projects.

def _get_gitversion( reporoot ):
    import subprocess
    #--always to not fail in a shallow clone:
    cmd=[ 'git','describe','--tags','--always',
          '--match','v[0-9]*.[0-9]*.[0-9]*' ]
    import os
    if os.environ.get('SIMPLEBUILD_GITVERSION_USE_LATEST_VTAG'):
        cmd += [ '--abbrev=0' ]
    p = subprocess.run( cmd,
                        cwd = reporoot,
                        capture_output = True )
    if p.returncode != 0:
        print(p.stderr.decode())
        print(p.stdout.decode())
        raise RuntimeError( f'Command "{" ".join(cmd)}" '
                            f'in dir {reporoot} failed!' )

    assert not p.stderr
    return p.stdout.decode().strip()

def guess_language( path ):
    if path.name=='pkg.info':
        return 'pkginfo'
    if path.name=='simplebuild.cfg':
        return 'toml'
    suf = path.suffix
    if suf in ('.cc','hh','icc'):
        return 'c++'
    if suf in ('.f',):
        return 'fortran'
    if suf in ('.c','h'):
        return 'c'
    if suf in ('.py',):
        return 'python'
    if not suf:
        lines = path.read_text().splitlines()
        if lines and lines[0].startswith('#!/'):
            return {
                '#!/usr/bin/env python3' : 'python',
                '#!/usr/bin/env bash' : 'bash',
            }.get(lines[0])

def get_display_language(language):
    if language == 'pkginfo':
        return ''
    if language in ('toml','bash'):
        return language.upper()
    return language.capitalize()

_fixuptest_dirrepl = []
def add_fixuptext_dirreplacement( adir, text ):
    _fixuptest_dirrepl.append( ( adir, text ) )

def fixuptext( pkgroot, txt ):
    import _simple_build_system
    import pathlib
    import os
    sbsdir = pathlib.Path(_simple_build_system.__file__).parent
    dirrepl = (_fixuptest_dirrepl or [])[:]
    dirrepl.append( ( pkgroot.parent, '/some/where/' ) )
    dirrepl.append( ( sbsdir.parent, '/some/where/else/' ) )

    cp = os.environ.get('CONDA_PREFIX')
    if cp:
        dirrepl.append( ( pathlib.Path(cp), '/conda/envs/sbenv/' ) )

    for p, t in dirrepl:
        txt = txt.replace( str(p.absolute())+'/', t )

    return txt

def check_output_contains( textfile, pattern, must_contain = True ):
    if (pattern in textfile.read_text()) == must_contain:
        return
    issue = 'does not contain' if must_contain else 'contains forbidden'
    print(f'\n\n\nERROR: File {textfile} {issue} pattern "{pattern}":\n')
    for e in textfile.read_text().splitlines(keepends=True):
        print(f'>>>{e}',end='')
    raise SystemExit(1)

def check_output_not_contains( textfile, pattern ):
    check_output_contains( textfile, pattern, must_contain = False )

