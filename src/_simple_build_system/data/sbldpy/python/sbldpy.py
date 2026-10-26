"""sbldpy: Simple Python bindings for C++ code, based on ctypes.

This is the pure-Python runtime of sbldpy. It loads the shared libraries of
modules defined in C++ with the header-only library sbldpy/sbldpy.hh, and
provides the functions and classes defined in them. The libraries
are not linked with libpython and do not use the Python C-API at all: they
only export the plain C functions sbldpy_abi_version, sbldpy_module_info,
sbldpy_call and sbldpy_last_error.

A module "mymod" consists of a library _sbldpy_mymod.so, and a small Python
file mymod.py next to it, containing:

    import sbldpy as _sbldpy
    _sbldpy.load_module( globals(), '_sbldpy_mymod' )

"""

import ctypes as _ct
import itertools as _itertools
import threading as _threading
import sys as _sys

__version__ = '0.1.0'
version_int = 1000#Ever increasing integer (major*1000000+minor*1000+patch)
abi_version = 1#Version of the binary interface with the modules

__all__ = [ 'load_module', 'module_info', 'abi_version', 'version_int' ]

_I64_MIN = -( 2**63 )
_I64_MAX = 2**63 - 1

#Error codes returned by sbldpy_call:
_EC_CALLBACK = 7
_ec2exc = { 1 : RuntimeError, 2 : ValueError, 3 : IndexError, 4 : TypeError,
            5 : OverflowError, 6 : MemoryError }

#Binary layout of data exchanged with the modules (see sbldpy.hh):
class _StrArg( _ct.Structure ):
    _fields_ = [ ( 'data', _ct.c_char_p ), ( 'size', _ct.c_int64 ) ]

class _StrRes( _ct.Structure ):
    _fields_ = [ ( 'data', _ct.c_void_p ), ( 'size', _ct.c_int64 ) ]

class _ArrArg( _ct.Structure ):
    _fields_ = [ ( 'data', _ct.c_void_p ), ( 'size', _ct.c_int64 ) ]

class _AssignRes( _ct.Structure ):
    _fields_ = [ ( 'dest', _ct.c_void_p ), ( 'assign', _ct.c_void_p ) ]

_AssignFct = _ct.CFUNCTYPE( _ct.c_int, _ct.c_void_p, _ct.c_void_p, _ct.c_int64 )
_TrampolineFct = _ct.CFUNCTYPE( _ct.c_int, _ct.c_uint64, _ct.POINTER( _ct.c_void_p ), _ct.c_void_p )
_ReleaseFct = _ct.CFUNCTYPE( None, _ct.c_uint64 )

_dtypes = { 'f64' : ( _ct.c_double, 'float64', 'd' ),
            'f32' : ( _ct.c_float, 'float32', 'f' ),
            'i8' : ( _ct.c_int8, 'int8', 'b' ),
            'i16' : ( _ct.c_int16, 'int16', 'h' ),
            'i32' : ( _ct.c_int32, 'int32', 'i' ),
            'i64' : ( _ct.c_int64, 'int64', 'q' ),
            'u8' : ( _ct.c_uint8, 'uint8', 'B' ),
            'u16' : ( _ct.c_uint16, 'uint16', 'H' ),
            'u32' : ( _ct.c_uint32, 'uint32', 'I' ),
            'u64' : ( _ct.c_uint64, 'uint64', 'Q' ) }

def _numpy( what ):
    try:
        import numpy
    except ImportError:
        raise ImportError( 'The Python module numpy is required for %s'%what )
    return numpy

################################################################################
# Conversion of values passed from Python to C++                              #
################################################################################

def _typename( v ):
    return type( v ).__name__

def _is_numpy_bool( v ):
    t = type( v )
    return t.__name__ in ( 'bool_', 'bool' ) and t.__module__ == 'numpy'

def _to_i64( v ):
    if isinstance( v, bool ) or _is_numpy_bool( v ):
        raise TypeError( 'expected int, got bool' )
    if not isinstance( v, int ):
        try:
            v = v.__index__()
        except AttributeError:
            raise TypeError( 'expected int, got %s'%_typename( v ) )
    if not ( _I64_MIN <= v <= _I64_MAX ):
        raise OverflowError( 'integer %i out of range (must fit in 64 bit signed integer)'%v )
    return v

def _to_f64( v ):
    if isinstance( v, float ):
        return v
    if isinstance( v, bool ) or _is_numpy_bool( v ):
        raise TypeError( 'expected float, got bool' )
    if isinstance( v, int ):
        return float( v )
    if isinstance( v, ( str, bytes ) ) or not hasattr( v, '__float__' ):
        if hasattr( v, '__index__' ):
            return float( v.__index__() )
        raise TypeError( 'expected float, got %s'%_typename( v ) )
    return float( v )

def _to_bool( v ):
    if v is True or v is False:
        return v
    raise TypeError( 'expected bool, got %s'%_typename( v ) )

def _to_str( v ):
    if not isinstance( v, str ):
        raise TypeError( 'expected str, got %s'%_typename( v ) )
    return v

def _conv_i64( v ):
    return _ct.c_int64( _to_i64( v ) )

def _conv_f64( v ):
    return _ct.c_double( _to_f64( v ) )

def _conv_bool( v ):
    return _ct.c_uint8( 1 if _to_bool( v ) else 0 )

def _conv_str( v ):
    b = _to_str( v ).encode( 'utf-8' )
    return _StrArg( b, len( b ) )

def _conv_cstr( v ):
    if '\0' in _to_str( v ):
        raise ValueError( 'string can not contain null characters' )
    return _conv_str( v )

def _is_numpy_array( v ):
    #Without importing numpy:
    return any( c.__name__ == 'ndarray' and c.__module__ == 'numpy' for c in type( v ).__mro__ )

def _make_conv_arr( dt, readonly ):
    #Arrays passed to C++ (as parameters or callback return values): Only numpy
    #arrays which can be used directly (without any conversion or copying) are
    #accepted:
    ctype, npname, _ = _dtypes[dt]
    itemsize = _ct.sizeof( ctype )
    #Expected __array_interface__ typestr (e.g. '<f8' or '|u1'):
    typestr = '%s%s%i'%( '|' if itemsize == 1 else ( '<' if _sys.byteorder == 'little' else '>' ),
                         dt[0], itemsize )
    if readonly:
        def fail( problem, hint ):
            raise TypeError( '%s (convert with e.g. %s)'%( problem, hint ) )
    else:
        def fail( problem, hint ):
            raise TypeError( '%s (this argument is filled by the C++ code, so allocate a'
                             ' writable, C-contiguous and one-dimensional numpy.%s array,'
                             ' e.g. with numpy.zeros(n, dtype=numpy.%s), keep a reference'
                             ' to it, and pass that)'%( problem, npname, npname ) )
    def conv( v ):
        if not _is_numpy_array( v ):
            if dt == 'u8' and isinstance( v, ( bytes, bytearray ) ):
                fail( 'expected numpy.uint8 array, got %s'%_typename( v ),
                      'numpy.frombuffer(x, dtype=numpy.uint8)' )
            fail( 'expected numpy.%s array, got %s'%( npname, _typename( v ) ),
                  'numpy.asarray(x, dtype=numpy.%s)'%npname )
        ai = v.__array_interface__
        if ai['typestr'] != typestr:
            fail( 'array has wrong element type (expected numpy.%s, got %s)'%( npname, v.dtype ),
                  'x.astype(numpy.%s)'%npname )
        shape = ai['shape']
        if len( shape ) != 1:
            fail( 'expected one-dimensional array (got %i dimensions)'%len( shape ), 'x.ravel()' )
        strides = ai['strides']
        if strides is not None and shape[0] > 1 and strides[0] != itemsize:
            fail( 'array is not C-contiguous', 'numpy.ascontiguousarray(x)' )
        data, ro = ai['data']
        if ro and not readonly:
            fail( 'array is read-only', 'x.copy()' )
        res = _ArrArg()
        res.data = data if shape[0] else None
        res.size = shape[0]
        res._keep = v
        return res
    return conv

def _check_seq( v, n ):
    if isinstance( v, ( str, bytes, dict ) ) or not hasattr( v, '__len__' ):
        raise TypeError( 'expected tuple of length %i, got %s'%( n, _typename( v ) ) )
    if len( v ) != n:
        raise TypeError( 'expected tuple of length %i, got length %i'%( n, len( v ) ) )

def _make_conv_tuple( convs ):
    n = len( convs )
    arrtype = _ct.c_void_p * n
    def conv( v ):
        _check_seq( v, n )
        elems = [ c( e ) for c, e in zip( convs, v ) ]
        res = arrtype( *[ _ct.addressof( e ) for e in elems ] )
        res._keep = elems
        return res
    return conv

class _ObjArg( _ct.c_void_p ):
    pass

def _make_conv_obj( clsref ):
    def conv( v ):
        cls = clsref[0]
        if type( v ) is not cls:
            raise TypeError( 'expected %s, got %s'%( cls.__name__, _typename( v ) ) )
        p = v._sbldpy_ptr
        if p is None:
            raise ValueError( '%s object is not initialised'%cls.__name__ )
        res = _ObjArg( p )
        res._keep = v
        return res
    return conv

################################################################################
# Callbacks                                                                   #
################################################################################

_tls = _threading.local()
_callbacks = {}
_next_token = _itertools.count( 1 )

class _CbToken( _ct.c_uint64 ):
    pass

def _make_conv_cb( argreaders, retwriter ):
    def conv_cb( v ):
        if not callable( v ):
            raise TypeError( 'expected callable, got %s'%_typename( v ) )
        token = next( _next_token )
        _callbacks[token] = ( v, argreaders, retwriter )
        return _CbToken( token )
    return conv_cb

def _trampoline( token, args, result ):
    try:
        fct, argreaders, retwriter = _callbacks[token]
        r = fct( *[ rd( args[i], None ) for i, rd in enumerate( argreaders ) ] )
        retwriter( r, result )
        return 0
    except BaseException as e:
        _tls.cb_exc = e
        return 1

def _release( token ):
    _callbacks.pop( token, None )

_trampoline_c = _TrampolineFct( _trampoline )
_release_c = _ReleaseFct( _release )

def _cbret_writer( d, info ):
    k = _kind( d )
    if k == 'none':
        return lambda v, addr : None
    if k == 'i64':
        def w( v, addr ):
            _ct.c_int64.from_address( addr ).value = _to_i64( v )
        return w
    if k == 'f64':
        def w( v, addr ):
            _ct.c_double.from_address( addr ).value = _to_f64( v )
        return w
    if k == 'bool':
        def w( v, addr ):
            _ct.c_uint8.from_address( addr ).value = 1 if _to_bool( v ) else 0
        return w
    if k in ( 'str', 'vec' ):
        #NB: getdata also returns an object keeping the data alive, which must
        #be kept until the data has been copied by the assign function:
        if k == 'str':
            def getdata( v ):
                b = _to_str( v ).encode( 'utf-8' )
                return b, len( b ), b
        else:
            arrconv = _make_conv_arr( d['dt'], True )
            def getdata( v ):
                a = arrconv( v )
                return a.data, a.size, a
        def w( v, addr ):
            data, n, keepalive = getdata( v )
            r = _AssignRes.from_address( addr )
            if _AssignFct( r.assign )( r.dest, data, n ) != 0:
                raise MemoryError()
            del keepalive
        return w
    if k == 'tuple':
        writers = [ _cbret_writer( e, info ) for e in d['items'] ]
        n = len( writers )
        arrtype = _ct.c_void_p * n
        def w( v, addr ):
            _check_seq( v, n )
            elems = arrtype.from_address( addr )
            for wi, ei, vi in zip( writers, elems, v ):
                wi( vi, ei )
        return w
    raise ImportError( 'unsupported callback return type: %r'%( d, ) )

################################################################################
# Conversion of values returned from C++ to Python                            #
################################################################################

class _Ret:
    """Allocates storage for a return value (alloc is None for void), and
    reads it from its address (read) or from the storage object (read_obj)"""
    def __init__( self, alloc, read, read_obj = None ):
        self.alloc = alloc
        self.read = read
        self.read_obj = read_obj or ( lambda obj, owner : read( _ct.addressof( obj ), owner ) )

def _read_scalar( ctype ):
    def read( addr, owner ):
        return ctype.from_address( addr ).value
    return read

def _read_str( addr, owner ):
    s = _StrRes.from_address( addr )
    return _ct.string_at( s.data, s.size ).decode( 'utf-8' ) if s.size else ''

def _make_read_arr( dt, is_view, readonly ):
    ctype, npname, _ = _dtypes[dt]
    def read( addr, owner ):
        np = _numpy( 'returning numpy arrays' )
        a = _ArrArg.from_address( addr )
        if a.size == 0 or not a.data:
            res = np.zeros( a.size, dtype = npname )
        elif is_view:
            buf = ( ctype * a.size ).from_address( a.data )
            buf._sbldpy_owner = owner#keep the Python object alive
            res = np.frombuffer( buf, dtype = npname )
        else:
            res = np.empty( a.size, dtype = npname )
            _ct.memmove( res.ctypes.data, a.data, a.size * _ct.sizeof( ctype ) )
        if readonly:
            res.flags.writeable = False
        return res
    return read

def _kind( d ):
    return d if isinstance( d, str ) else d['k']

def _make_ret( d, classes, allow = ( 'obj', 'view' ) ):
    k = _kind( d )
    if k == 'none':
        return _Ret( None, lambda addr, owner : None )
    scalar = { 'int' : _ct.c_int64, 'uint' : _ct.c_uint64, 'f64' : _ct.c_double }.get( k )
    if scalar:
        return _Ret( scalar, _read_scalar( scalar ), lambda obj, owner : obj.value )
    if k == 'bool':
        return _Ret( _ct.c_uint8, lambda addr, owner : _ct.c_uint8.from_address( addr ).value != 0,
                     lambda obj, owner : obj.value != 0 )
    if k == 'str':
        return _Ret( _StrRes, _read_str )
    if k == 'copy' or ( k == 'view' and 'view' in allow ):
        if d['dt'] not in _dtypes:
            raise ImportError( 'unsupported array type: %r'%( d, ) )
        return _Ret( _ArrArg, _make_read_arr( d['dt'], k == 'view', d.get( 'ro', False ) ) )
    if k == 'tuple':
        items = [ _make_ret( e, classes, allow = () ) for e in d['items'] ]
        n = len( items )
        arrtype = _ct.c_void_p * n
        def alloc():
            elems = [ ( i.alloc or _ct.c_void_p )() for i in items ]
            res = arrtype( *[ _ct.addressof( e ) for e in elems ] )
            res._keep = elems
            return res
        def read( addr, owner ):
            elems = arrtype.from_address( addr )
            return tuple( i.read( e, owner ) for i, e in zip( items, elems ) )
        return _Ret( alloc, read )
    if k == 'obj' and 'obj' in allow:
        clsref = _classref( classes, d['cls'] )
        def read( addr, owner ):
            return _wrap_object( clsref[0], _ct.c_void_p.from_address( addr ).value )
        return _Ret( _ct.c_void_p, read, lambda obj, owner : _wrap_object( clsref[0], obj.value ) )
    raise ImportError( 'unsupported return type: %r'%( d, ) )

def _classref( classes, name ):
    #Classes are created after the converters, so refer to them indirectly:
    if name not in classes:
        raise ImportError( 'unknown class: %s'%name )
    return classes[name]

def _make_conv( d, classes ):
    k = _kind( d )
    simple = { 'i64' : _conv_i64, 'f64' : _conv_f64, 'bool' : _conv_bool,
               'str' : _conv_str, 'cstr' : _conv_cstr }.get( k )
    if simple:
        return simple
    if k == 'arr':
        if d['dt'] not in _dtypes:
            raise ImportError( 'unsupported array type: %r'%( d, ) )
        return _make_conv_arr( d['dt'], d.get( 'ro', True ) )
    if k == 'tuple':
        return _make_conv_tuple( [ _make_conv( e, classes ) for e in d['items'] ] )
    if k == 'obj':
        return _make_conv_obj( _classref( classes, d['cls'] ) )
    if k == 'cb':
        argreaders = [ _make_ret( e, classes, allow = () ).read for e in d['args'] ]
        return _make_conv_cb( argreaders, _cbret_writer( d['ret'], classes ) )
    raise ImportError( 'unsupported parameter type: %r'%( d, ) )

################################################################################
# Calling functions in the modules                                            #
################################################################################

class _Lib:
    """A loaded module library"""

    def __init__( self, path ):
        try:
            self.cdll = _ct.CDLL( path, mode = getattr( _ct, 'RTLD_LOCAL', 0 ) )
        except OSError as e:
            raise ImportError( 'Could not load sbldpy module library %s: %s'%( path, e ) )
        try:
            f_abi = self.cdll.sbldpy_abi_version
        except AttributeError:
            raise ImportError( 'Not an sbldpy module library: %s'%path )
        f_abi.restype = _ct.c_int
        f_abi.argtypes = []
        v = f_abi()
        if v != abi_version:
            raise ImportError( ( 'The sbldpy module library %s was built for sbldpy ABI version %i,'
                                 ' but the sbldpy runtime (version %s) supports ABI version %i.'
                                 ' The module must be rebuilt.' )%( path, v, __version__, abi_version ) )
        self.path = path
        f = self.cdll.sbldpy_module_info
        f.restype = _ct.c_char_p
        f.argtypes = []
        self._info = f
        f = self.cdll.sbldpy_call
        f.restype = _ct.c_int
        f.argtypes = [ _ct.c_int, _ct.c_void_p, _ct.c_void_p ]
        self.call = f
        f = self.cdll.sbldpy_last_error
        f.restype = _ct.c_char_p
        f.argtypes = []
        self.last_error = f

    def info( self ):
        import json
        s = self._info()
        if s is None:
            raise ImportError( self.last_error().decode( 'utf-8', errors = 'replace' ) )
        return json.loads( s.decode( 'utf-8' ) )

    def raise_error( self, ec ):
        #An exception raised in a callback is stored until the C++ code
        #returns (it is discarded if the C++ code returns another error, but
        #kept until the next error if the C++ code catches the CallbackError
        #and returns normally):
        exc = getattr( _tls, 'cb_exc', None )
        _tls.cb_exc = None
        if ec == _EC_CALLBACK:
            if exc is not None:
                raise exc
            raise RuntimeError( self.last_error().decode( 'utf-8', errors = 'replace' ) )
        exccls = _ec2exc.get( ec, RuntimeError )
        if exccls is MemoryError:
            raise MemoryError()
        raise exccls( self.last_error().decode( 'utf-8', errors = 'replace' ) )

#TODO (performance, parked): A call with scalar arguments currently costs about
#1.7us, of which only about 0.35us is the ctypes call itself. If modules with
#many tiny calls in hot loops appear (e.g. per-step accessors in Griff, or
#per-entry histogram filling), consider: (1) generating a single Python
#function doing conversions and call (instead of two levels), with inline fast
#paths for int and float arguments (about 1.2us), and (2) reusing per-function
#ctypes Structure buffers (pointer array, arguments and result) taken from a
#small pool, which keeps it thread and reentrancy safe (about 0.7us). The ABI
#and sbldpy.hh would not change.
def _make_caller( lib, fid, convs, ret ):
    """Returns function call(values,owner=None) calling function fid in the
    library with the given values (converted with convs), returning the
    result. The owner is kept alive by numpy arrays viewing data in it. For
    efficiency, the code is generated specifically for the number of
    parameters."""
    n = len( convs )
    ns = { '_libcall' : lib.call, '_raise' : lib.raise_error, '_fid' : fid,
           '_A' : _ct.c_void_p * max( 1, n ), '_addressof' : _ct.addressof,
           '_alloc' : ret.alloc, '_read' : ret.read_obj, '_release_tokens' : _release_tokens }
    for i, c in enumerate( convs ):
        ns['_c%i'%i] = c
    lines = [ 'def call( values, owner = None ):' ]
    if n:
        lines.append( '    %s, = values'%', '.join( 'v%i'%i for i in range( n ) ) )
    convlines = [ '    s%i = _c%i( v%i )'%( i, i, i ) for i in range( n ) ]
    if any( c.__name__ == 'conv_cb' for c in convs ):
        #Release callbacks registered before a failed conversion:
        lines += [ '    s = []', '    try:' ]
        lines += [ '    ' + line + '; s.append( s%i )'%i for i, line in enumerate( convlines ) ]
        lines += [ '    except BaseException:', '        _release_tokens( s )', '        raise' ]
    else:
        lines += convlines
    lines.append( '    args = _A( %s )'%', '.join( '_addressof( s%i )'%i for i in range( n ) ) )
    if ret.alloc is None:
        lines += [ '    ec = _libcall( _fid, args, None )',
                   '    if ec:', '        _raise( ec )' ]
    else:
        lines += [ '    res = _alloc()',
                   '    ec = _libcall( _fid, args, _addressof( res ) )',
                   '    if ec:', '        _raise( ec )',
                   '    return _read( res, owner )' ]
    exec( '\n'.join( lines ) + '\n', ns )
    return ns['call']

def _release_tokens( storage ):
    for s in storage:
        if isinstance( s, _CbToken ):
            _release( s.value )

def _wrap_object( cls, ptr ):
    o = cls.__new__( cls )
    o._sbldpy_ptr = ptr
    return o

################################################################################
# Creating functions and classes                                              #
################################################################################

def _check_name( name, what ):
    import keyword
    if not isinstance( name, str ) or not name.isidentifier() or keyword.iskeyword( name ):
        raise ImportError( 'Invalid %s name: %r'%( what, name ) )
    if name.startswith( '_sbld' ):
        raise ImportError( 'Invalid %s name (names starting with "_sbld" are reserved): %r'%( what, name ) )

class _Annot:
    """Type annotation shown in help"""
    def __init__( self, s ):
        self.s = s
    def __repr__( self ):
        return self.s

_annot_dtypes = dict( ( k, 'numpy.typing.NDArray[numpy.%s]'%v[1] ) for k, v in _dtypes.items() )

def _typestr( d, mode ):
    """Python type of parameters (mode='param') or return values (mode='ret')
    and similar for callbacks (mode='cbret', and cb args use 'ret')"""
    k = _kind( d )
    if k in ( 'i64', 'int', 'uint' ):
        return 'int'
    if k == 'f64':
        return 'float'
    if k == 'bool':
        return 'bool'
    if k in ( 'str', 'cstr' ):
        return 'str'
    if k == 'none':
        return 'object' if mode == 'cbret' else 'None'
    if k in ( 'arr', 'vec', 'copy', 'view' ):
        return _annot_dtypes[d['dt']]
    if k == 'tuple':
        return 'tuple[%s]'%', '.join( _typestr( e, mode ) for e in d['items'] )
    if k == 'obj':
        return d['cls']
    if k == 'cb':
        return 'collections.abc.Callable[[%s], %s]'%( ', '.join( _typestr( e, 'ret' ) for e in d['args'] ),
                                                       _typestr( d['ret'], 'cbret' ) )
    return 'object'

class _FuncSpec:
    """Information about a function, method, or constructor"""

    def __init__( self, fi, classes, nself = 0 ):
        self.name = fi['name']
        self.doc = fi.get( 'doc', '' )
        self.id = fi['id']
        self.params = fi['params']
        self.ret = fi['ret']
        names = fi.get( 'argnames' )
        #Without argument names, arguments are positional only:
        self.positional_only = names is None
        if names is None:
            names = [ 'arg%i'%i for i in range( len( self.params ) ) ]
        if len( names ) != len( self.params ):
            raise ImportError( 'Inconsistent argument names of %s'%self.name )
        self.argnames = names
        for a in self.argnames:
            _check_name( a, 'argument' )
        if len( set( self.argnames ) ) != len( self.argnames ) or ( nself and 'self' in self.argnames ):
            raise ImportError( 'Duplicate argument names of %s'%self.name )
        self.convs = [ _make_conv( p, classes ) for p in self.params ]

    def signature_src( self, with_self ):
        parts = ( [ 'self' ] if with_self else [] ) + self.argnames
        if self.positional_only and self.argnames:
            parts.append( '/' )
        return ', '.join( parts )

    def annotations( self ):
        a = dict( ( n, _Annot( _typestr( p, 'param' ) ) ) for n, p in zip( self.argnames, self.params ) )
        a['return'] = _Annot( _typestr( self.ret, 'ret' ) )
        return a

def _make_function( spec, caller, modname, qualname, with_self, body = None, extra_ns = None ):
    """Creates Python function with the proper signature, calling caller"""
    args = ', '.join( spec.argnames )
    if body is None:
        if with_self:
            body = 'return _sbld_call( ( self, %s ), self )'%args
        else:
            body = 'return _sbld_call( ( %s ) )'%( args + ',' if spec.argnames else '' )
    src = 'def %s( %s ):\n    %s\n'%( spec.name if spec.name.isidentifier() else 'f',
                                       spec.signature_src( with_self ), body )
    ns = { '_sbld_call' : caller }
    ns.update( extra_ns or {} )
    exec( src, ns )
    f = ns[ spec.name if spec.name.isidentifier() else 'f' ]
    f.__name__ = spec.name
    f.__qualname__ = qualname
    f.__module__ = modname
    f.__doc__ = spec.doc or None
    f.__annotations__ = spec.annotations()
    return f

def _no_subclass( cls, **kwargs ):
    raise TypeError( 'sbldpy classes can not be subclassed' )

def _no_copy( self, *args ):
    raise TypeError( '%s objects can not be copied or pickled'%type( self ).__name__ )

def _make_class( lib, ci, classes, modname ):
    name = ci['name']
    cls = classes[name][0]
    dtor = _make_caller( lib, ci['dtor'], [ lambda p : _ct.c_void_p( p ) ], _make_ret( 'none', classes ) )

    def __del__( self, _dtor = dtor ):
        p = getattr( self, '_sbldpy_ptr', None )
        if p is not None:
            self._sbldpy_ptr = None
            _dtor( ( p, ) )
    cls.__del__ = __del__

    #Constructor (returns a pointer to the new object):
    if ci['init'] is None:
        def __init__( self, *args, **kwargs ):
            raise TypeError( '%s objects can not be created directly'%name )
        __init__.__qualname__ = name + '.__init__'
    else:
        spec = _FuncSpec( ci['init'], classes )
        ccall = _make_caller( lib, spec.id, spec.convs,
                              _Ret( _ct.c_void_p, None, lambda obj, owner : obj.value ) )
        body = ( 'p = _sbld_call( ( %s ) )\n'
                 '    _sbld_set( self, p )'%( ', '.join( spec.argnames ) + ',' if spec.argnames else '' ) )
        __init__ = _make_function( spec, ccall, modname, name + '.__init__', True, body = body,
                                   extra_ns = { '_sbld_set' : _set_ptr } )
        __init__.__annotations__['return'] = _Annot( 'None' )
    __init__.__module__ = modname
    cls.__init__ = __init__

    for fi in ci['methods']:
        spec = _FuncSpec( fi, classes, nself = 1 )
        _check_name( spec.name, 'method' )
        convs = [ _make_conv( { 'k' : 'obj', 'cls' : name }, classes ) ] + spec.convs
        caller = _make_caller( lib, spec.id, convs, _make_ret( spec.ret, classes ) )
        setattr( cls, spec.name, _make_function( spec, caller, modname, '%s.%s'%( name, spec.name ), True ) )
    for fi in ci['staticmethods']:
        spec = _FuncSpec( fi, classes )
        _check_name( spec.name, 'static method' )
        caller = _make_caller( lib, spec.id, spec.convs, _make_ret( spec.ret, classes, allow = ( 'obj', ) ) )
        setattr( cls, spec.name, staticmethod( _make_function( spec, caller, modname,
                                                                '%s.%s'%( name, spec.name ), False ) ) )
    return cls

def _set_ptr( self, p ):
    old = getattr( self, '_sbldpy_ptr', None )
    self._sbldpy_ptr = p
    if old is not None:
        #Re-initialisation of existing object:
        o = _wrap_object( type( self ), old )
        del o

class _Module:
    """A loaded module"""

    def __init__( self, path, modname, defname ):
        lib = _Lib( path )
        info = lib.info()
        if info.get( 'module' ) != defname:
            raise ImportError( 'The sbldpy module library %s provides module "%s" and not "%s"'%(
                path, info.get( 'module' ), defname ) )
        self.lib = lib
        self.info = info
        self.modname = modname
        hidden = info['hidden']
        self._shutdown = _make_caller( lib, hidden['shutdown'], [], _make_ret( 'none', {} ) )
        ns = {}
        classes = {}
        for ci in info['classes']:
            _check_name( ci['name'], 'class' )
            if ci['name'] in classes:
                raise ImportError( 'Duplicate class name: %s'%ci['name'] )
            cls = type( ci['name'], (), { '__slots__' : ( '_sbldpy_ptr', '__weakref__' ),
                                          '__doc__' : ci.get( 'doc' ) or None,
                                          '__module__' : modname,
                                          '__qualname__' : ci['name'],
                                          '__init_subclass__' : classmethod( _no_subclass ),
                                          '__reduce__' : _no_copy,
                                          '__reduce_ex__' : _no_copy } )
            classes[ci['name']] = [ cls ]
            ns[ci['name']] = cls
        for ci in info['classes']:
            _make_class( lib, ci, classes, modname )
        for fi in info['functions']:
            spec = _FuncSpec( fi, classes )
            _check_name( spec.name, 'function' )
            if spec.name in ns:
                raise ImportError( 'Duplicate name in module %s: %s'%( modname, spec.name ) )
            caller = _make_caller( lib, spec.id, spec.convs, _make_ret( spec.ret, classes, allow = ( 'obj', ) ) )
            ns[spec.name] = _make_function( spec, caller, modname, spec.name, False )
        self.namespace = ns
        init = _make_caller( lib, hidden['init_runtime'], [ _ct.c_void_p, _ct.c_void_p ],
                             _make_ret( 'none', {} ) )
        init( ( _ct.cast( _trampoline_c, _ct.c_void_p ).value, _ct.cast( _release_c, _ct.c_void_p ).value ) )

    def shutdown( self ):
        self._shutdown( () )

_loaded = {}
_shutdown_registered = [ False ]

def _atexit_shutdown():
    #Callbacks still held by C++ code must not be called or released after
    #shutdown of the Python interpreter:
    for m in list( _loaded.values() ):
        try:
            m.shutdown()
        except Exception:
            pass

def _load( path, modname, defname ):
    m = _Module( path, modname, defname )
    if not _shutdown_registered[0]:
        import atexit
        atexit.register( _atexit_shutdown )
        _shutdown_registered[0] = True
    _loaded[modname] = m
    return m

def load_module( module_globals, libname, defname = None ):
    """Load the sbldpy module library with the given name (located next to the
    module file), and put its contents into the given globals() dictionary of
    the module. The defname is the name given to SBLDPY_MODULE(..) in the
    library (by default the last part of the name of the module)."""
    import os
    modname = module_globals['__name__']
    if defname is None:
        defname = modname.rsplit( '.', 1 )[-1]
    path = os.path.join( os.path.dirname( os.path.abspath( module_globals['__file__'] ) ), libname + '.so' )
    m = _load( path, modname, defname )
    module_globals.update( m.namespace )
    module_globals['__all__'] = sorted( m.namespace.keys() )
    if m.info.get( 'doc' ):
        module_globals['__doc__'] = m.info['doc']

def module_info( mod ):
    """Information about a loaded sbldpy module (given as module object or
    name), as provided by the module library: versions of sbldpy used to build
    it, functions, classes, etc."""
    import copy
    name = mod if isinstance( mod, str ) else getattr( mod, '__name__', None )
    m = _loaded.get( name )
    if m is None:
        raise ValueError( 'Not a loaded sbldpy module: %r'%( mod, ) )
    return copy.deepcopy( m.info )
