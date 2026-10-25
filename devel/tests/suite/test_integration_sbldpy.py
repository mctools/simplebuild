# Tests of sbldpy modules (pymod_* subdirs), which provide Python bindings via
# ctypes, without compiling against Python headers or linking with libpython.

import platform
import shutil
import sys

import pytest

from sbtestutils import require_feature, run, write_files

pytestmark = pytest.mark.integration

_datadir = __import__('pathlib').Path(__file__).parent / 'data_sbldpy'

_files = {
    'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
    'PkgA/pkg.info' : 'package()\n',
    'PkgA/libinc/A.hh' : 'int a_value();\n',
    'PkgA/libsrc/A.cc' : '#include "PkgA/A.hh"\nint a_value() { return 17; }\n',
    'PkgA/python/purepy.py' : 'value = 42\n',
    'PkgB/pkg.info' : 'package(USEPKG PkgA)\n',
    'PkgB/pymod_small/mod.cc' : ( '#include "sbldpy/sbldpy.hh"\n'
                                  'SBLDPY_MODULE( small ) { m.def( "value", []() { return 1; } ); }\n' ),
}

def _have_numpy():
    try:
        import numpy # noqa F401
        return True
    except ImportError:
        return False

def inst( d ):
    return d / 'simplebuild_cache' / 'install'

@pytest.fixture( scope = 'module' )
def proj( tmp_path_factory ):
    d = tmp_path_factory.mktemp( 'sbldpy' ) / 'proj'
    write_files( d, _files )
    write_files( d, { 'PkgA/pymod_feat/feat.cc' : ( _datadir / 'feat.cc' ).read_text() } )
    write_files( d, {
        'PkgG/pkg.info' : 'package()\n',
        #Global variables named like the module object (e.g. CLHEP units brought
        #into the global namespace by G4SystemOfUnits.hh) must not trigger
        #-Wshadow errors:
        'PkgG/pymod_globnames/mod.cc' : ( 'namespace Units { constexpr double m = 1.0; constexpr double s = 2.0; }\n'
                                        'using Units::m;\n'
                                        'using Units::s;\n'
                                        '#include "sbldpy/sbldpy.hh"\n'
                                        'SBLDPY_MODULE( globnames ) {\n'
                                        '  m.def( "meter", []() { return ::m; } );\n'
                                        '  m.def( "second", []() { return s; } );\n'
                                        '}\n' ),
    } )
    run( 'sb', d )
    return d

def check( d, *sections ):
    res = run( [ 'sbenv', sys.executable, _datadir / 'check.py' ] + list( sections ), d )
    for s in sections:
        assert f'check {s} OK' in res.stdout
    assert not res.stderr.strip()

def test_installed_files( proj ):
    i = inst( proj )
    assert ( i / 'python' / 'sbldpy.py' ).is_file()
    assert ( i / 'sbldpy' / 'include' / 'sbldpy' / 'sbldpy.hh' ).is_file()
    assert sorted( f.name for f in ( i / 'python' / 'PkgA' ).iterdir() if f.name != '__pycache__' ) \
        == [ '__init__.py', '_sbldpy_feat.so', 'feat.py', 'purepy.py' ]
    assert sorted( f.name for f in ( i / 'python' / 'PkgB' ).iterdir() if f.name != '__pycache__' ) \
        == [ '__init__.py', '_sbldpy_small.so', 'small.py' ]
    stub = ( i / 'python' / 'PkgA' / 'feat.py' ).read_text()
    assert "_sbldpy.load_module( globals(), '_sbldpy_feat', 'feat' )" in stub

def test_basic( proj ):
    check( proj, 'basic' )

def test_arrays( proj ):
    check( proj, 'arrays' )

def test_numpy( proj ):
    require_feature( 'numpy', _have_numpy() )
    check( proj, 'numpy' )

def test_classes( proj ):
    check( proj, 'classes' )

def test_callbacks( proj ):
    check( proj, 'callbacks' )

def test_other_module( proj ):
    res = run( [ 'sbenv', sys.executable, '-c',
                 'import PkgB.small, PkgA.purepy; print(PkgB.small.value(), PkgA.purepy.value)' ], proj )
    assert res.stdout.strip() == '1 42'

def test_global_names( proj ):
    res = run( [ 'sbenv', sys.executable, '-c',
                 'import PkgG.globnames as g; print(g.meter(), g.second())' ], proj )
    assert res.stdout.strip() == '1.0 2.0'

def test_no_python_dependency( proj ):
    #Not compiled with Python flags:
    mf = ( proj / 'simplebuild_cache' / 'bld' / 'makefiles' / 'Makefile_PkgA.make' ).read_text()
    lines = [ line for line in mf.splitlines() if 'pymod_feat/feat.cc' in line and ' -c ' in line ]
    assert len( lines ) == 1
    assert 'PYBIND11' not in lines[0] and 'ython' not in lines[0]
    #Not compiled with hidden visibility (see flagfct_pymod in conf.py):
    assert '-fvisibility' not in lines[0]
    lib = inst( proj ) / 'python' / 'PkgA' / '_sbldpy_feat.so'
    #Not linked with libpython:
    if platform.system() == 'Darwin':
        deps = run( [ 'otool', '-L', lib ], proj ).stdout
    else:
        deps = run( [ 'ldd', lib ], proj ).stdout
    assert 'libPKG__PkgA' in deps
    #(NB: the path of the library itself contains "python", so check for the
    #actual Python libraries):
    assert 'libpython' not in deps.lower() and 'python.framework' not in deps.lower()
    #The four sbldpy_* functions used by the runtime are exported:
    nm = shutil.which( 'nm' )
    if nm:
        args = [ nm, '-gU', lib ] if platform.system() == 'Darwin' else [ nm, '-D', '--defined-only', lib ]
        syms = set( line.split()[-1].lstrip( '_' ) for line in run( args, proj ).stdout.splitlines()
                    if line.strip() )
        assert set( [ 'sbldpy_abi_version', 'sbldpy_module_info',
                      'sbldpy_call', 'sbldpy_last_error' ] ).issubset( syms )

def test_abi_mismatch( proj ):
    code = ( 'import sbldpy\nsbldpy.abi_version = 999\n'
             'try:\n    import PkgA.feat\nexcept ImportError as e:\n    print(e)\n' )
    res = run( [ 'sbenv', sys.executable, '-c', code ], proj )
    assert 'was built for sbldpy ABI version 1, but the sbldpy runtime' in res.stdout
    assert 'supports ABI version 999' in res.stdout and 'must be rebuilt' in res.stdout

def _build_errors( d, files, expected_msg ):
    write_files( d, files )
    res = run( 'sb', d, expect_ec = None )
    assert res.ec != 0
    assert expected_msg in res.out, res.out
    for f in files:
        p = d / f
        p.unlink()
        if not any( p.parent.iterdir() ):
            p.parent.rmdir()
    run( 'sb', d )

def test_build_errors( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, _files )
    run( 'sb', d )
    _mod = '#include "sbldpy/sbldpy.hh"\nSBLDPY_MODULE( %s ) {\n%s\n}\n'
    #Reserved and invalid names:
    _build_errors( d, { 'PkgA/python/_sbldx.py' : '' }, 'names starting with "_sbld" are reserved' )
    _build_errors( d, { 'PkgA/pycpp__sbldx/mod.cc' : '' }, 'names starting with "_sbld" are reserved' )
    _build_errors( d, { 'PkgA/pymod_9x/mod.cc' : _mod%('x','') }, 'Invalid name of sbldpy module directory' )
    _build_errors( d, { 'PkgA/pymod_class/mod.cc' : _mod%('class','') }, 'can not be a Python keyword' )
    _build_errors( d, { 'PkgA/pymod_purepy/mod.cc' : _mod%('purepy','') },
                   'Python module PkgA.purepy is provided in both sbldpy (pymod_purepy/) and pure'
                   ' (python/purepy.py) forms' )
    _build_errors( d, { 'PkgB/pymod_small2/mod.cc' : _mod%('small2',''),
                        'PkgB/pycpp_small2/mod.cc' : '' },
                   'Python module PkgB.small2 is provided in both' )
    _build_errors( d, { 'Sbldpy/pkg.info' : 'package()\n' }, 'Invalid package name: "Sbldpy"' )
    #Errors in the C++ code detected at compile time:
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('y','') },
                   'name in SBLDPY_MODULE(..) must match the name of the module' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('x','m.def("f",[](float){});') },
                   'float is not supported as parameter type (use double)' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('x','m.def("f",[](int){});') },
                   'integers can only be received as std::int64_t' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('x','m.def("f",[](){ return std::vector<double>(); });') },
                   'std::vector can not be returned directly' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('x','m.def("f",[](){ static double x; return &x; });') },
                   'pointers can not be returned' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : _mod%('x','m.def("f",[](std::string_view){});') },
                   'std::string_view is not supported (use std::string or const char*)' )
    _build_errors( d, { 'PkgA/pymod_x/mod.cc' : ( '#include "sbldpy/sbldpy.hh"\nstruct B{ int f() const { return 1; } };\n'
                                                  'struct D : B {};\n'
                                                  'SBLDPY_MODULE( x ) { m.add_class<D>("D").def("f",&D::f); }\n' ) },
                   'methods must be member functions of the class itself' )

_nimporterrors = [ 0 ]
def _import_error( d, files, expected_msg ):
    #NB: Each case uses a module with a different name (PkgA.x1, PkgA.x2, ...),
    #since a new file in the same location might otherwise not be recompiled
    #on platforms where make only considers modification times with a
    #resolution of one second:
    _nimporterrors[0] += 1
    n = 'x%i'%_nimporterrors[0]
    def fix( s ):
        return s.replace( 'pymod_x/', f'pymod_{n}/' ).replace( 'SBLDPY_MODULE( x )', f'SBLDPY_MODULE( {n} )' )
    files = dict( ( fix( k ), fix( v ) ) for k, v in files.items() )
    expected_msg = expected_msg.replace( 'PkgA.x:', f'PkgA.{n}:' )
    write_files( d, files )
    run( 'sb', d )
    res = run( [ 'sbenv', sys.executable, '-c', f'import PkgA.{n}' ], d, expect_ec = None )
    assert res.ec != 0
    assert expected_msg in res.out, res.out
    for f in files:
        p = d / f
        p.unlink()
        if not any( p.parent.iterdir() ):
            p.parent.rmdir()

def test_import_errors( tmp_path ):
    #Errors in the module definition detected when the module is loaded:
    d = tmp_path / 'proj'
    write_files( d, _files )
    _mod = '#include "sbldpy/sbldpy.hh"\nSBLDPY_MODULE( x ) {\n%s\n}\n'
    _import_error( d, { 'PkgA/pymod_x/mod.cc' : _mod%'m.def("f",[](std::int64_t){},{"a","b"});' },
                   'wrong number of argument names given for f' )
    _import_error( d, { 'PkgA/pymod_x/mod.cc' : _mod%'m.def("f",[](){});m.def("f",[](){});' },
                   'Duplicate name in module PkgA.x: f' )
    _import_error( d, { 'PkgA/pymod_x/mod.cc' : _mod%'m.def("f",[](std::int64_t){},{"class"});' },
                   "Invalid argument name: 'class'" )
    _import_error( d, { 'PkgA/pymod_x/mod.cc' : ( '#include "sbldpy/sbldpy.hh"\nstruct S{ S(std::int64_t){} };\n'
                                                  'SBLDPY_MODULE( x ) { m.add_class<S>("S").def_init<std::int64_t>()'
                                                  '.def_init<std::int64_t>(); }\n' ) },
                   'only one constructor can be defined for class S' )
    _import_error( d, { 'PkgA/pymod_x/mod.cc' : ( '#include "sbldpy/sbldpy.hh"\nstruct S{};\n'
                                                  'SBLDPY_MODULE( x ) { m.def("f",[](const S&){}); }\n' ) },
                   'was not added to the module with add_class' )

def test_deinstall( tmp_path ):
    d = tmp_path / 'proj'
    write_files( d, _files )
    run( 'sb', d )
    pydir = inst( d ) / 'python' / 'PkgB'
    assert ( pydir / 'small.py' ).is_file()
    assert run( 'sbenv python3 -c "import PkgB.small;print(PkgB.small.value())"', d ).stdout.strip() == '1'
    #Removing a module removes all its installed files:
    shutil.rmtree( d / 'PkgB' / 'pymod_small' )
    run( 'sb', d )
    assert not pydir.exists()
    ( d / 'PkgB' / 'python' ).mkdir()
    ( d / 'PkgB' / 'python' / 'other.py' ).write_text( '' )
    run( 'sb', d )
    assert sorted( f.name for f in pydir.iterdir() ) == [ '__init__.py', 'other.py' ]

def test_special_module_names( tmp_path ):
    #pymod__init -> __init__.py, pymod__main -> __main__.py, and pymod__<name>
    #-> _<name>.py:
    d = tmp_path / 'proj'
    _mod = '#include "sbldpy/sbldpy.hh"\nSBLDPY_MODULE( %s ) { %s }\n'
    write_files( d, {
        'simplebuild.cfg' : '[bundle]\nname = "proj"\n',
        'PkgC/pkg.info' : 'package()\n',
        'PkgC/pymod__init/mod.cc' : _mod%( '_init', 'm.doc("PkgC doc"); m.def("initvalue",[](){ return 1; });' ),
        'PkgC/pymod__main/mod.cc' : '#include <cstdio>\n' + _mod%( '_main', (
            'm.def("mainvalue",[](){ return 2; });'
            'm.def("main",[](){ std::printf("in main\\n"); return std::int64_t(7); });' ) ),
        'PkgC/pymod__helper/mod.cc' : _mod%( '_helper', 'm.def("helpervalue",[](){ return 3; });' ),
        'PkgC/pymod_empty/mod.cc' : _mod%( 'empty', '' ),
        'PkgC/python/wrapper.py' : 'from ._helper import helpervalue\n',
    } )
    run( 'sb', d )
    pydir = inst( d ) / 'python' / 'PkgC'
    assert sorted( f.name for f in pydir.iterdir() if f.name != '__pycache__' ) == [
        '__init__.py', '__main__.py', '_helper.py', '_sbldpy__helper.so',
        '_sbldpy__init.so', '_sbldpy__main.so', '_sbldpy_empty.so', 'empty.py', 'wrapper.py' ]
    code = ( 'import PkgC, PkgC.__main__, PkgC._helper, PkgC.wrapper, PkgC.empty;'
             'print(PkgC.initvalue(), PkgC.__main__.mainvalue(), PkgC._helper.helpervalue(),'
             ' PkgC.wrapper.helpervalue(), PkgC.__doc__)' )
    assert run( [ 'sbenv', sys.executable, '-c', code ], d ).stdout.strip() == '1 2 3 3 PkgC doc'
    #Running the package executes the main function in __main__.py:
    res = run( [ 'sbenv', sys.executable, '-m', 'PkgC' ], d, expect_ec = 7 )
    assert res.stdout == 'in main\n'
    #Without pymod__init, the __init__.py file is again generated automatically:
    shutil.rmtree( d / 'PkgC' / 'pymod__init' )
    run( 'sb', d )
    assert not ( pydir / '_sbldpy__init.so' ).exists()
    code = 'import PkgC, PkgC.wrapper; print(hasattr(PkgC,"initvalue"), PkgC.wrapper.helpervalue())'
    assert run( [ 'sbenv', sys.executable, '-c', code ], d ).stdout.strip() == 'False 3'
    #Invalid and clashing names:
    _build_errors( d, { 'PkgC/pymod___x/mod.cc' : _mod%( '__x', '' ) },
                   'Invalid name of sbldpy module directory PkgC/pymod___x/' )
    _build_errors( d, { 'PkgC/pymod__sbldx/mod.cc' : _mod%( '_sbldx', '' ) },
                   'names starting with "_sbld" are reserved' )
    _build_errors( d, { 'PkgC/pymod__init/mod.cc' : _mod%( '_init', '' ),
                        'PkgC/python/__init__.py' : '' },
                   'The file __init__.py of package PkgC is provided by both pymod__init/ and python/__init__.py' )
    _build_errors( d, { 'PkgC/pymod__init/mod.cc' : _mod%( '_init', '' ),
                        'PkgC/pycpp__init/mod.cc' : '' },
                   'The file __init__.py of package PkgC is provided by both pymod__init/ and pycpp__init/' )
    _build_errors( d, { 'PkgC/python/__main__.py' : '' },
                   'The file __main__.py of package PkgC is provided by both pymod__main/ and python/__main__.py' )
    _build_errors( d, { 'PkgC/python/_helper.py' : '' },
                   'Python module PkgC._helper is provided in both sbldpy (pymod__helper/) and pure'
                   ' (python/_helper.py) forms' )
