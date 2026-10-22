# Usage of simplebuild in the style of the development tools of projects like
# NCrystal (the "ncdevtool sb/sbrun/sbenv" commands in mctools/ncrystal):
#
# * The main cfg file is selected with SIMPLEBUILD_CFG (so the current working
#   directory does not matter), and has a dummy pkg_root, a relative cachedir,
#   and depends on bundles found via its search_path.
# * One of these bundles has its packages created by a dynamic_generator
#   script, and adds a directory with a command to the PATH via env_paths.
# * The code is built with "unwrapped_simplebuild --quiet", and commands are
#   then launched with sbenv.
# * A compiled application locates the shared library of the package relative
#   to its own location (like ncrystal-config does), and a Python module uses
#   that application to find and load the library.

import pytest

from sbtestutils import run, write_files

pytestmark = pytest.mark.integration

_cfg_main = '''[bundle]
  pkg_root = './dummy'
[depend]
  bundles= [ 'mydynamic', 'mystatic' ]
  search_path = [ "../", "../static" ]
[build]
  cachedir = '../simplebuild_cache/cache_cfg_reldbg'
  mode = 'reldbg'
'''

_cfg_dynamic = '''[bundle]
  name = 'mydynamic'
  dynamic_generator = './sbgenerate.py'
  pkg_root = './autogen/pkgs'
  env_paths = [ "MYDEV_DATA_PATH:<install>/data",
                "PATH:../../devel/bin" ]
'''

_cfg_static = '''[bundle]
  name = 'mystatic'
'''

#Application printing the directory with the shared libraries, determined
#relative to the location of the application itself:
_app_config = r'''
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <string>
#ifdef __APPLE__
#  include <mach-o/dyld.h>
#else
#  include <unistd.h>
#endif
static std::string exe_path()
{
  char buf[PATH_MAX+1];
#ifdef __APPLE__
  uint32_t size = sizeof(buf);
  if ( _NSGetExecutablePath( buf, &size ) != 0 )
    return {};
#else
  auto n = readlink( "/proc/self/exe", buf, PATH_MAX );
  if ( n <= 0 )
    return {};
  buf[n] = '\0';
#endif
  char resolved[PATH_MAX+1];
  if ( !realpath( buf, resolved ) )
    return {};
  return resolved;
}
int main()
{
  std::string p = exe_path();
  if ( p.empty() )
    return 1;
  auto bindir = p.substr( 0, p.rfind('/') );
  std::printf( "%s/../lib\n", bindir.c_str() );
  return 0;
}
'''

_pymod = '''
import ctypes
import pathlib
import subprocess

def _load_lib():
    out = subprocess.run( [ 'sb_genlib_config' ], capture_output = True,
                          check = True ).stdout.decode().strip()
    libs = list( pathlib.Path(out).glob('*PKG__GenLib.*') )
    if not libs:
        raise RuntimeError(f'Could not locate the GenLib shared library in {out}')
    return ctypes.CDLL( str(libs[0]) )

def value():
    return _load_lib().genlib_value()
'''

#The dynamic generator script, creating the GenLib package:
_generator = f'''
import pathlib
root = pathlib.Path(__file__).resolve().absolute().parent / 'autogen' / 'pkgs'
pkg = root / 'GenLib'
files = {{
    'pkg.info' : 'package()\\n',
    'libinc/genlib.hh' : 'extern "C" int genlib_value();\\n',
    'libsrc/genlib.cc' : '#include "GenLib/genlib.hh"\\nint genlib_value() {{ return 42; }}\\n',
    'app_config/main.cc' : {_app_config!r},
    'python/__init__.py' : {_pymod!r},
    'data/somedata.txt' : 'some data\\n',
}}
for relpath, content in files.items():
    f = pkg / relpath
    f.parent.mkdir( parents = True, exist_ok = True )
    if not f.exists() or f.read_text() != content:
        f.write_text( content )
'''

@pytest.fixture
def devrepo( tmp_path ):
    repo = tmp_path / 'repo'
    sbdir = repo / 'devel' / 'simplebuild'
    write_files( repo, {
        'devel/simplebuild/cfgs/simplebuild_reldbg.cfg' : _cfg_main,
        'devel/simplebuild/cfgs/dummy/README' : 'Dummy pkg_root\n',
        'devel/simplebuild/simplebuild.cfg' : _cfg_dynamic,
        'devel/simplebuild/sbgenerate.py' : _generator,
        'devel/simplebuild/static/simplebuild.cfg' : _cfg_static,
        'devel/simplebuild/static/StaticPkg/pkg.info' : 'package(USEPKG GenLib)\n',
        'devel/simplebuild/static/StaticPkg/scripts/testgenlib' : (
            '#!/usr/bin/env python3\nimport GenLib\nprint("value:",GenLib.value())\n' ),
        'devel/simplebuild/static/StaticPkg/scripts/testgenlib.log' : 'value: 42\n',
        'devel/bin/mydevtool' : '#!/usr/bin/env bash\necho "mydevtool ok"\n',
    } )
    for f in ( sbdir / 'static' / 'StaticPkg' / 'scripts' / 'testgenlib',
               repo / 'devel' / 'bin' / 'mydevtool' ):
        f.chmod( 0o755 )
    #Commands are launched from an unrelated directory:
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    env = { 'SIMPLEBUILD_CFG' : str( sbdir / 'cfgs' / 'simplebuild_reldbg.cfg' ) }
    return repo, elsewhere, env

def test_apps_find_files_relative_to_their_location( devrepo ):
    #Applications must be installed in the bin directory of the installation
    #(not merely symlinked from there), since applications like ncrystal-config
    #locate other files (e.g. ../lib) relative to their own location:
    repo, elsewhere, env = devrepo
    run( [ 'unwrapped_simplebuild', '--quiet' ], elsewhere, env_extra = env )
    inst = ( repo / 'devel' / 'simplebuild' / 'simplebuild_cache'
             / 'cache_cfg_reldbg' / 'install_reldbg' )
    app = inst / 'bin' / 'sb_genlib_config'
    assert app.is_file() and not app.is_symlink()
    res = run( [ 'sbenv', 'sb_genlib_config' ], elsewhere, env_extra = env )
    libdir = res.stdout.strip()
    assert ( inst / 'lib' ).samefile( libdir )
