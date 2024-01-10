# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'simplebuild'
copyright = '2013-2024, ESS ERIC and simplebuild developers'
author = 'Thomas Kittelmann'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # 'myst_parser', #for parsing .md files?
    'sphinxarg.ext',
    'sphinx_toolbox.sidebar_links',
    'sphinx_toolbox.github',
    'sphinx_toolbox.collapse',
    #'sphinx_licenseinfo',
    ]

github_username = 'mctools'
github_repository = 'simplebuild'

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output #noqa E501

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
#html_logo = 'icon/favicon-32x32.png'
html_favicon = 'icon/favicon-32x32.png'
#html_sidebars = { '**': ['globaltoc.html', 'searchbox.html'] }

html_theme_options = {
    'logo_only': False,
#    'collapse_navigation' : False,
    'sticky_navigation': True, #sidebar stays in place while contents scrolls
    'navigation_with_keys': True, #navigate with left/right arrow keys
    #'github_url' : 'https://github.com/mctools/simplebuild',
}

#html_theme_options = {
#    'logo': 'icon/android-chrome-192x192.png',
#    # etc.
#}
#

#html_sidebars = { '**': ['globaltoc.html', 'relations.html',
#                         'sourcelink.html', 'searchbox.html'] }



#html_theme_options = {
#    ...
#    "home_page_in_toc": True
#    ...
#}
#


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

def prepare_projectexample_dir():
    import pathlib
    import shutil
    confpydir = pathlib.Path(__file__).parent
    blddir = confpydir.parent / 'build'
    assert blddir.exists()
    root_src = confpydir.parent / 'example_project'
    assert (root_src/'simplebuild.cfg').is_file()
    root = blddir / 'autogen_copy' / root_src.name
    already_done = root.is_dir()
    if not already_done:
        root.parent.mkdir()
        shutil.copytree( root_src, root )
    class dirs:
        pass
    d = dirs()
    d.root = root
    d.blddir = blddir
    d.confpydir = confpydir
    d.already_done = already_done
    return d

def generate_projectexample_rst( dirs ):
    #Get all files in the example, in a manner which puts
    #simplebuild.cfg/pkg.info files first, and ignores caches etc.:
    if dirs.already_done:
        return
    files = [ dirs.root/'simplebuild.cfg' ]
    pkginfo_files = []
    for rd in sorted(dirs.root.iterdir()):
        if rd.is_dir() and rd.name!='simplebuild_cache':
            pkginfo_files += list(sorted(rd.glob('**/pkg.info')))
    def ignorefile(f):
        return ( f.name.startswith('.')
                 or any(e in f.name for e in '~#^') )
    for pf in pkginfo_files:
        files.append(pf)
        for f in sorted(pf.parent.rglob('*')):
            if ( f.is_file()
                 and not pf.samefile(f)
                 and not ignorefile(f) ):
                files.append(f)

    res=''

    for f in files:
        language = guess_language(f)
        if language is None:
            raise RuntimeError(f'Could not guess language of {f}')
        display_language = get_display_language(language)
        if display_language:
            display_language = f' ({display_language})'
        fn = f.relative_to(dirs.root.parent)
        #trick to highlight comments in pkg.info:
        syntaxhl_language = 'sh' if language=='pkginfo' else language
        res += f'''
* **{fn}**{display_language}

'''
        if len(f.read_text().splitlines())<999:
            res += f'''
  .. literalinclude:: ../{fn}
    :language: {syntaxhl_language}
'''
        else:
            res +=  f'''  .. collapse:: (show file)

    .. literalinclude:: ../{fn}
      :language: {syntaxhl_language}


'''
    (dirs.confpydir.parent / 'build'
     / 'autogen_projectexample_files.rst').write_text(res)

def fixuptext( dirs, txt ):
    import _simple_build_system
    import pathlib
    import os
    txt = txt.replace( str(dirs.root.parent.absolute())+'/', '/some/where/' )
    sbsdir = pathlib.Path(_simple_build_system.__file__).parent
    txt = txt.replace( str(sbsdir.parent.absolute())+'/', '/some/where/else/' )
    cp = os.environ.get('CONDA_PREFIX')
    if cp:
        cp = pathlib.Path(cp).absolute()
        txt = txt.replace( str(cp)+'/', '/conda/envs/sbenv/' )

    return txt

def invoke_cmd(dirs,
               cmd,
               cwd,
               outfile,
               hidden_sbenv=False,
               fake_add_eval_envsetup=False,
               timings=False):
    import subprocess
    import shlex
    import os
    if outfile.exists():
        print(f' ---> Skipping command "{cmd}" '
              f'since {outfile.name} was found.')
        return

    print(f' ---> Launching command "{cmd}" ')
    import time
    t0 = time.time()
    cmdlist = shlex.split(cmd)
    if fake_add_eval_envsetup or hidden_sbenv:
        cmdlist = ['sbenv'] + cmdlist
    env = os.environ.copy()
    env['PYTHONUNBUFFERED']='1'
    p = subprocess.run( cmdlist,
                        cwd = cwd,
                        capture_output = True,
                        env = env )
    dt = time.time() - t0
    if p.returncode != 0:
        print(p.stderr.decode())
        print(p.stdout.decode())
        raise RuntimeError(f'Command "{cmd}" in dir {cwd} failed!')
    print(f'Done running cmd {cmd}')
    assert not p.stderr
    txt = fixuptext( dirs, p.stdout.decode() )
    txt = f'$> {cmd}\n' + txt
    if timings:
        txt += f'[last command took {dt:.2f} seconds to complete] $>\n'

    if fake_add_eval_envsetup:
        txt = '$> eval "$(sb --env-setup)"\n'+ txt

    outfile.write_text(txt)

def generate_projectexample_command_outputs( dirs ):
    if dirs.already_done:
        return
    assert not ( dirs.root / 'simplebuild_cache' ).exists()
    #shutil.rmtree( root / 'simplebuild_cache',
    #               ignore_errors = True )
    newfile = dirs.root / 'SomePkgB'/'scripts'/'newcmd'
    assert newfile.parent.is_dir()
    newfile.unlink(missing_ok=True)

    invoke_cmd( dirs,
                'sb',
                dirs.root,
                dirs.blddir / 'autogen_projectexample_cmdout_sb.txt',
                timings = True )

    invoke_cmd( dirs,
                'sb',
                dirs.root,
                dirs.blddir / 'autogen_projectexample_cmdout_sb2.txt',
                timings = True )


    filetotouch = dirs.root / 'SomePkgC'/'app_foobar'/'main.cc'
    assert filetotouch.is_file()
    filetotouch.touch()

    newfilecontent = ( dirs.confpydir.parent
                       / 'example_project_newcmd_content').read_text()
    assert newfile.parent.is_dir()
    newfile.write_text( newfilecontent )
    import stat
    newfile.chmod(newfile.stat().st_mode | stat.S_IEXEC)

    invoke_cmd( dirs,
                'sb',
                dirs.root,
                dirs.blddir / 'autogen_projectexample_cmdout_sb3.txt',
                timings = True )

    invoke_cmd( dirs,
                'sb_somepkgc_foobar',
                dirs.root,
                dirs.blddir / 'autogen_projectexample_cmdout_foobar.txt',
                fake_add_eval_envsetup = True )

    othercmds = [
        "sb_somepkga_mycmd",
        "python3 -c 'import SomePkgA.foo; SomePkgA.foo.somefunc()'",
        "python3 -c 'import SomePkgA.bar; SomePkgA.bar.somecppfunc()'",
        "sb_somepkgb_mycmd",
        "sb_somepkgb_newcmd",
        ]
    for i,c in enumerate(othercmds):
        invoke_cmd( dirs,
                    c,
                    dirs.root,
                    dirs.blddir / f'autogen_projectexample_cmdout_other{i}.txt',
                    hidden_sbenv = True )

_pe_dirs = prepare_projectexample_dir()
generate_projectexample_rst( _pe_dirs)
generate_projectexample_command_outputs( _pe_dirs )
