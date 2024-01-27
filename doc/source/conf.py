 # Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import pathlib
import subprocess
import shutil
import shlex
import time
import stat
from _simple_build_system._sphinxutils import _get_gitversion


project = 'simplebuild'
copyright = '2013-2024, ESS ERIC and simplebuild developers'
author = 'Thomas Kittelmann'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

nitpicky = True
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

if 'SIMPLEBUILD_CFG' in os.environ:
    del os.environ['SIMPLEBUILD_CFG']

def _reporoot():
    p=pathlib.Path(__file__).parent.parent.parent
    assert ( p / 'src' / '_simple_build_system'/ '__init__.py' ).is_file()
    return p.absolute()

version = _get_gitversion( _reporoot() )

def generate_sbinit_in_empty_dir():
    confpydir = pathlib.Path(__file__).parent
    blddir = confpydir.parent / 'build'
    blddir.mkdir(exist_ok=True)
    sbinitdir = blddir / 'autogen_freshsbinit'
    if sbinitdir.is_dir():
        return#already done
    sbinitdir.mkdir()
    print(' ---> Launching command sb --init ')
    subprocess.run( ['sb','--init'],
                    cwd = sbinitdir,
                    check = True )
    assert ( sbinitdir / 'simplebuild.cfg' ).is_file()

def prepare_projectexample_dir():
    confpydir = pathlib.Path(__file__).parent
    blddir = confpydir.parent / 'build'
    blddir.mkdir(exist_ok=True)
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

    from _simple_build_system._sphinxutils import  ( guess_language,
                                                     get_display_language )
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


def invoke_cmd(pkgroot,
               cmd,
               cwd,
               outfile,
               timings=False,
               hidden_sbenv = False ):
    cmdlauncher = ( pathlib.Path(__file__).parent.parent
                    / 'cmdlauncherwithshellsnippet.x' ).absolute()
    assert cmdlauncher.is_file()

    if outfile.exists():
        print(f' ---> Skipping command "{cmd}" '
              f'since {outfile.name} was found.')
        return

    print(f' ---> Launching command "{cmd}" ')
    t0 = time.time()
    cmdlist = shlex.split(cmd)
    if hidden_sbenv:
        cmdlist = ['sbenv'] + cmdlist
    cmdlist = [str(cmdlauncher)] + cmdlist
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
    from _simple_build_system._sphinxutils import fixuptext
    txt = fixuptext( pkgroot, p.stdout.decode() )
    txt = f'$> {cmd}\n' + txt
    if timings:
        txt += f'[last command took {dt:.2f} seconds to complete] $>\n'

    outfile.write_text(txt)

def generate_projectexample_command_outputs( dirs ):
    if dirs.already_done:
        return
    from _simple_build_system._sphinxutils import ( check_output_not_contains,
                                                    check_output_contains )


    assert not ( dirs.root / 'simplebuild_cache' ).exists()
    #shutil.rmtree( root / 'simplebuild_cache',
    #               ignore_errors = True )
    newfile = dirs.root / 'SomePkgB'/'scripts'/'newcmd'
    assert newfile.parent.is_dir()
    assert not newfile.exists()

    newtestfile = dirs.root / 'SomePkgA'/'scripts'/'testfoo'
    assert newtestfile.parent.is_dir()
    assert not newtestfile.exists()

    of = dirs.blddir / 'autogen_projectexample_cmdout_sb.txt'
    invoke_cmd( dirs.root,
                'sb',
                dirs.root,
                of,
                timings = True )
    msg_envsetup = 'sb --env-setup'
    msg_cmake = 'Inspecting environment via CMake'
    check_output_not_contains( of, msg_envsetup )
    check_output_contains( of, msg_cmake )

    of = dirs.blddir / 'autogen_projectexample_cmdout_sb2.txt'
    invoke_cmd( dirs.root,
                'sb',
                dirs.root,
                of,
                timings = True )
    check_output_not_contains( of, msg_envsetup )
    check_output_not_contains( of, msg_cmake )

    filetotouch = dirs.root / 'SomePkgC'/'app_foobar'/'main.cc'
    assert filetotouch.is_file()
    filetotouch.touch()

    newfilecontent = ( dirs.confpydir.parent
                       / 'example_project_newcmd_content').read_text()
    assert newfile.parent.is_dir()
    newfile.write_text( newfilecontent )
    newfile.chmod(newfile.stat().st_mode | stat.S_IEXEC)

    of = dirs.blddir / 'autogen_projectexample_cmdout_sb3.txt'
    invoke_cmd( dirs.root,
                'sb',
                dirs.root,
                of,
                timings = True )
    check_output_not_contains( of, msg_envsetup )
    check_output_not_contains( of, msg_cmake )

    check_output_contains( of, 'Creating application sb_somepkgc_foobar' )

    of = dirs.blddir / 'autogen_projectexample_cmdout_foobar.txt'
    invoke_cmd( dirs.root,
                'sb_somepkgc_foobar',
                dirs.root,
                of,
                hidden_sbenv = True )

    check_output_not_contains( of, msg_envsetup )
    check_output_not_contains( of, msg_cmake )

    othercmds = [
        "sb_somepkga_mycmd",
        "python3 -c 'import SomePkgA.foo; SomePkgA.foo.somefunc()'",
        "python3 -c 'import SomePkgA.bar; SomePkgA.bar.somecppfunc()'",
        "sb_somepkgb_mycmd",
        "sb_somepkgb_newcmd",
        ]
    for i,c in enumerate(othercmds):
        invoke_cmd( dirs.root,
                    c,
                    dirs.root,
                    dirs.blddir / f'autogen_projectexample_cmdout_other{i}.txt',
                    hidden_sbenv = True )


    newtestfilecontent = ( dirs.confpydir.parent
                       / 'example_project_newtestcmd_content').read_text()
    assert newtestfile.parent.is_dir()
    newtestfile.write_text( newtestfilecontent )
    newtestfile.chmod(newtestfile.stat().st_mode | stat.S_IEXEC)

    of = dirs.blddir / 'autogen_projectexample_cmdout_sbtests.txt'
    invoke_cmd( dirs.root,
                'sb --tests',
                dirs.root,
                of,
                timings = True,
                hidden_sbenv = True )
    check_output_not_contains( of, msg_envsetup )
    check_output_not_contains( of, msg_cmake )
    check_output_contains( of, 'All tests completed without failures!')

    #not related to the project example, but we need their output as well:
    invoke_cmd( dirs.root,
                'sbenv --help',
                dirs.root,
                dirs.blddir / 'autogen_sbenv_help.txt' )
    invoke_cmd( dirs.root,
                'sbrun --help',
                dirs.root,
                dirs.blddir / 'autogen_sbrun_help.txt' )

#    invoke_cmd( dirs.root,
#                'sb --init core_val',
#                sbverify_dir,
#                dirs.blddir / 'autogen_sbverify1.txt' )
#    invoke_cmd( dirs.root,
#                'sb --tests',
#                sbverify_dir,
#                dirs.blddir / 'autogen_sbverify2.txt' )
#
#
#
#    sbverify_dir = dirs.blddir / 'autogen_sbverify'
#    sbverify_dir.mkdir()


def generate_sbverify():
    confpydir = pathlib.Path(__file__).parent
    script = confpydir.parent / 'cmdlauncher_sbverify.x'
    assert script.is_file()
    blddir = confpydir.parent / 'build'
    blddir.mkdir(exist_ok=True)
    outfile = blddir / 'autogen_sbverify_cmdout.txt'
    workdir = blddir / 'autogen_sbverify'
    if workdir.is_dir():
        return#already done
    workdir.mkdir()
    cmd=str(script.absolute())
    print(f' ---> Launching command {cmd}')
    env = os.environ.copy()
    env['PYTHONUNBUFFERED']='1'
    p = subprocess.run( [cmd],
                        cwd = workdir,
                        check = True,
                        capture_output = True )
    class dirs:
        pass
    dirs = dirs()
    dirs.root = workdir / 'sbverify'
    assert ( dirs.root / 'simplebuild.cfg' ).is_file()
    assert not p.stderr
    from _simple_build_system._sphinxutils import ( fixuptext,
                                                    check_output_contains )
    txt = fixuptext( dirs.root, p.stdout.decode() )
    txt = '\n'.join( e.replace('CMDPROMPT>','(sbenv) $> ')
                     for e in txt.splitlines() )
    txt = '$> conda activate sbenv\n' + txt
    outfile.write_text(txt)
    check_output_contains( outfile, 'All tests completed without failures!')

_pe_dirs = prepare_projectexample_dir()
generate_projectexample_rst( _pe_dirs)
generate_projectexample_command_outputs( _pe_dirs )
generate_sbinit_in_empty_dir()
generate_sbverify()
