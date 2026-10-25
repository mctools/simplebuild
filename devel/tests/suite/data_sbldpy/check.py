# Checks of the sbldpy module defined in feat.cc (used in
# test_integration_sbldpy.py). Usage: check.py <section>

import array
import gc
import sys
import threading
import traceback

import sbldpy
from PkgA import feat

def expect( exc, fct, *args, match = None, **kwargs ):
    try:
        fct( *args, **kwargs )
    except exc as e:
        if match is not None:
            assert match in str( e ), ( match, str( e ) )
        return e
    raise AssertionError( 'expected %s from %r'%( exc.__name__, fct ) )

def check_basic():
    assert feat.__doc__ == 'Module for testing sbldpy'
    assert feat.__all__ == sorted( feat.__all__ ) and 'add' in feat.__all__
    assert feat.add( 1, 2 ) == 3.0 and feat.add( b = 3, a = 1 ) == 4.0
    expect( TypeError, feat.add, 1 )
    assert type( feat.add( 1, 2 ) ) is float
    assert feat.iadd( 2**62, 2**62 - 1 ) == 2**63 - 1
    assert feat.iadd( -2**63, 0 ) == -2**63
    expect( OverflowError, feat.iadd, 2**63, 0 )
    expect( OverflowError, feat.iadd, -2**63 - 1, 0 )
    expect( TypeError, feat.iadd, 1.0, 1, match = 'expected int, got float' )
    expect( TypeError, feat.iadd, True, 1, match = 'expected int, got bool' )
    expect( TypeError, feat.iadd, '1', 1 )
    expect( TypeError, feat.iadd, 1 )
    expect( TypeError, feat.iadd, 1, 2, 3 )
    expect( TypeError, feat.iadd, arg0 = 1, arg1 = 2 )#positional only
    assert feat.u64max() == 2**64 - 1 and feat.i64min() == -2**63
    assert feat.i8() == -5 and feat.u16() == 65535 and feat.plainint() == -7 and feat.plainunsigned() == 7
    assert feat.halfvalue() == 0.5
    expect( TypeError, feat.add, True, 1, match = 'expected float, got bool' )
    expect( TypeError, feat.add, '1', 1 )
    expect( OverflowError, feat.add, 10**400, 1 )
    assert feat.negate( True ) is False and feat.negate( False ) is True
    expect( TypeError, feat.negate, 1 )
    expect( TypeError, feat.negate, None )
    assert feat.nothing() is None
    assert feat.greet( 'wørld' ) == 'Hello wørld' and feat.greet( name = '' ) == 'Hello '
    assert feat.clen( 'abc' ) == 3 and feat.strvalue( 'a\0b' ) == 'a\0b' and feat.strvalue( 'dé' ) == 'dé'
    expect( ValueError, feat.clen, 'a\0b' )
    expect( TypeError, feat.greet, b'x' )
    assert feat.tup( ( 1, 2, 3 ) ) == ( 3, 'abc', ( 6.0, True ) )
    assert feat.tup( [ 1, 2, 3.5 ] ) == ( 3, 'abc', ( 6.5, True ) )
    assert feat.tup( a = ( 1, 1, 0.5 ) ) == ( 3, 'abc', ( 2.5, True ) )
    expect( TypeError, feat.tup, ( 1, 2 ) )
    expect( TypeError, feat.tup, 'abc' )
    assert feat.tupin( ( 5, 'x', ( False, 1 ) ) ) == '5xF'
    expect( TypeError, feat.tupin, ( 5, 'x', ( 1, 1 ) ) )
    for i, exc in enumerate( ( ValueError, IndexError, TypeError, OverflowError, MemoryError,
                               RuntimeError, RuntimeError ) ):
        e = expect( exc, feat.fail, i )
        assert str( e ) == ( 'bad value', 'out of range', 'bad type', 'overflow', '',
                             'unknown C++ exception', 'runtime problem' )[i]
    assert feat.square( 3 ) == 9.0
    assert feat.a_value() == 17
    assert feat.sbldpy_version() == sbldpy.version_int
    assert feat.sbldpy_version_str() == sbldpy.__version__
    v = [ int( e ) for e in sbldpy.__version__.split( '.' ) ]
    assert sbldpy.version_int == v[0] * 1000000 + v[1] * 1000 + v[2]
    info = sbldpy.module_info( feat )
    assert info['module'] == 'feat' and info['sbldpy_version'] == sbldpy.version_int
    assert info['abi_version'] == sbldpy.abi_version
    assert sbldpy.module_info( 'PkgA.feat' ) == info
    expect( ValueError, sbldpy.module_info, 'PkgA.nonexisting' )
    #Signatures and documentation:
    import inspect
    assert str( inspect.signature( feat.add ) ) == '(a: float, b: float) -> float'
    assert str( inspect.signature( feat.iadd ) ) == '(arg0: int, arg1: int, /) -> int'
    assert feat.add.__doc__ == 'Add two numbers' and feat.add.__module__ == 'PkgA.feat'
    assert feat.a_value.__doc__ == 'Value from the package library'
    assert 'Callable[[float], float]' in str( inspect.signature( feat.integrate ) )

def check_arrays():
    #Input arrays (does not need numpy):
    assert feat.sum( [ 1, 2, 3.5 ] ) == 6.5 and feat.sum( ( 1.0, ) ) == 1.0 and feat.sum( [] ) == 0.0
    assert feat.sum( array.array( 'd', [ 1, 2 ] ) ) == 3.0
    assert feat.sum( memoryview( array.array( 'd', [ 1, 2, 3, 4 ] ) )[::2] ) == 4.0
    assert feat.sum( ( x * 0.5 for x in range( 4 ) ) ) == 3.0
    expect( TypeError, feat.sum, array.array( 'f', [ 1, 2 ] ), match = 'wrong element type' )
    expect( TypeError, feat.sum, 'abc' )
    expect( TypeError, feat.sum, [ 1, 'a' ] )
    expect( TypeError, feat.sum, 5 )
    assert feat.isum( [ 1, 2, 3 ] ) == 6 and feat.isum( array.array( 'q', [ 2**62, 2**62 - 1 ] ) ) == 2**63 - 1
    expect( TypeError, feat.isum, [ 1.5 ] )
    expect( TypeError, feat.isum, [ True ] )
    expect( TypeError, feat.isum, array.array( 'i', [ 1 ] ) )
    assert feat.bsum( b'\x01\x02' ) == 3 and feat.bsum( bytearray( b'\x05' ) ) == 5
    assert feat.bsum( memoryview( b'\x07\x01' ) ) == 8 and feat.bsum( [ 255, 1 ] ) == 256
    assert feat.bsum( b'' ) == 0
    expect( ValueError, feat.bsum, [ 256 ] )
    expect( TypeError, feat.bsum, array.array( 'd', [ 1 ] ) )

def check_numpy():
    import numpy as np
    assert feat.sum( np.arange( 4.0 ) ) == 6.0 and feat.sum( np.arange( 10.0 )[::2] ) == 20.0
    ro = np.arange( 3.0 )
    ro.flags.writeable = False
    assert feat.sum( ro ) == 3.0 and feat.sum( np.zeros( 0 ) ) == 0.0
    expect( TypeError, feat.sum, np.arange( 3, dtype = np.float32 ), match = 'wrong element type' )
    expect( TypeError, feat.sum, np.zeros( ( 2, 2 ) ), match = 'one-dimensional' )
    assert feat.isum( np.arange( 5 ) ) == 10
    expect( TypeError, feat.isum, np.arange( 5, dtype = np.int32 ) )
    expect( TypeError, feat.isum, np.arange( 5, dtype = np.uint64 ) )
    assert feat.bsum( np.array( [ 1, 2 ], dtype = np.uint8 ) ) == 3
    expect( TypeError, feat.bsum, np.array( [ 1, 2 ], dtype = np.int8 ) )
    assert feat.iadd( np.int32( 5 ), np.int64( 6 ) ) == 11 and feat.add( np.float32( 0.5 ), np.int64( 1 ) ) == 1.5
    expect( TypeError, feat.negate, np.bool_( False ) )
    expect( TypeError, feat.iadd, np.bool_( True ), 1 )
    a = feat.linspace( 0, 1, 5 )
    assert a.dtype == np.float32 and a.flags.writeable and list( a ) == [ 0, 0.25, 0.5, 0.75, 1.0 ]
    m = feat.ints()
    assert m.dtype == np.int32 and m.shape == ( 3, ) and list( m ) == [ 1, 2, 3 ]
    b = feat.rawbytes()
    assert b.dtype == np.uint8 and b.tobytes() == b'\x00\x01\xff'
    e = feat.empty()
    assert e.dtype == np.float64 and e.shape == ( 0, )
    arr, n = feat.tuparr()
    assert list( arr ) == [ 1.0, 2.0 ] and n == 2
    assert feat.tup( np.arange( 3.0 ) ) == ( 3, 'abc', ( 3.0, True ) )
    #Views keep the owner alive:
    c = feat.Counter( 3 )
    c.record()
    c.increment( 1 )
    c.record()
    h = c.history()
    assert list( h ) == [ 3.0, 4.0 ] and not h.flags.writeable
    expect( ValueError, h.__setitem__, 0, 1.0 )
    hw = c.history_rw()
    assert hw.flags.writeable
    hw[0] = 42.0
    assert list( c.history() ) == [ 42.0, 4.0 ]
    del c, hw
    gc.collect()
    assert list( h ) == [ 42.0, 4.0 ]
    assert feat.cbvec( lambda a : list( a ) + [ a.sum() ] ) == 4
    assert feat.cbvec( lambda a : np.zeros( 10 ) ) == 10
    assert feat.cbbytes( lambda : np.array( [ 1, 2 ], dtype = np.uint8 ) ) == 3

def check_classes():
    c = feat.Counter( 5 )
    assert repr( c ) == 'Counter(5)' and c.increment( 1 ) == 6 and c.increment( n = 10 ) == 16
    assert c.value() == 16
    c.set_value( v = 3 )
    assert c.value() == 3
    expect( TypeError, c.set_value, 'x' )
    expect( TypeError, c.increment )
    assert feat.Counter( start = 2 ).value() == 2
    expect( TypeError, feat.Counter )
    expect( TypeError, feat.Counter, 1, 2 )
    assert feat.Counter.increment.__doc__ == 'Increment'
    assert feat.Counter.__doc__ == 'A counter' and feat.Counter.__module__ == 'PkgA.feat'
    assert repr( feat.make_counter( 4 ) ) == 'Counter(40)' and repr( feat.Counter.make( v = 2 ) ) == 'Counter(20)'
    assert feat.counter_value( feat.Counter( 7 ) ) == 7
    c = feat.Counter( 1 )
    feat.counter_bump( c )
    assert c.value() == 2
    expect( TypeError, feat.counter_value, 5, match = 'expected Counter, got int' )
    expect( TypeError, feat.counter_value, feat.Tracked() )
    expect( TypeError, type, 'Sub', ( feat.Counter, ), {} )
    import copy
    import pickle
    expect( TypeError, copy.copy, c )
    expect( TypeError, copy.deepcopy, c )
    expect( TypeError, pickle.dumps, c )
    c.__init__( 100 )
    assert c.value() == 100
    #Objects are deleted with the Python objects:
    n0 = feat.ninstances()
    objs = [ feat.Tracked() for i in range( 10 ) ]
    assert feat.ninstances() == n0 + 10
    del objs
    gc.collect()
    assert feat.ninstances() == n0
    #Classes without constructor:
    expect( TypeError, feat.NoInit, match = 'can not be created directly' )
    assert feat.make_noinit().value() == 5
    expect( TypeError, feat.Counter.increment, feat.Tracked(), 1 )
    import inspect
    assert str( inspect.signature( feat.Counter.increment ) ) == '(self, n: int) -> int'
    assert str( inspect.signature( feat.Counter.__init__ ) ) == '(self, start: int) -> None'

def bad_callback( x ):
    raise KeyError( 'inside callback' )

def check_callbacks():
    assert abs( feat.integrate( lambda x : x * x, 1000 ) - 1 / 3 ) < 1e-6
    assert feat.integrate( lambda x : 1, n = 10 ) == 1.0
    assert feat.integrate( lambda x : True if False else 2, 1 ) == 2.0
    e = expect( KeyError, feat.integrate, bad_callback, 10 )
    tb = ''.join( traceback.format_exception( type( e ), e, e.__traceback__ ) )
    assert 'bad_callback' in tb and 'inside callback' in tb
    expect( TypeError, feat.integrate, lambda x : 'abc', 10, match = 'expected float, got str' )
    expect( TypeError, feat.integrate, 5, 10, match = 'expected callable' )
    expect( SystemExit, feat.integrate, lambda x : sys.exit( 3 ), 10 )
    assert feat.cbstr( lambda s, n : s * n ) == 'xxx!'
    assert feat.cbargs( lambda *a : repr( a ) ) == repr( ( 2**64 - 1, -3, 0.25, True, 'cstr', ( 5, 'tuple' ) ) )
    assert feat.cbtup( lambda t : ( t[0] * 2, str( t[1] ) ) ) == ( 14, '0.5' )
    expect( TypeError, feat.cbtup, lambda t : ( 1, 2 ) )
    expect( TypeError, feat.cbtup, lambda t : ( 1, ) )
    assert feat.cbbytes( lambda : b'\x01\x02\x03' ) == 6 and feat.cbbytes( lambda : [ 1 ] ) == 1
    #Returned data must be kept alive until it has been copied (with lists of
    #various sizes, freed memory would likely be reused):
    for n in range( 1, 300 ):
        assert feat.cbbytes( lambda : [ 1 ] * n ) == n
    assert feat.cbbool( lambda i : i == 1 ) is True
    expect( TypeError, feat.cbbool, lambda i : 1 )
    #Exceptions swallowed by the C++ code are discarded:
    assert feat.cbcatch( lambda : bad_callback( 1 ) ) == 1
    assert feat.add( 1, 1 ) == 2.0
    expect( ValueError, feat.fail, 0 )
    #Callbacks are released when the C++ code no longer holds them:
    assert len( sbldpy._callbacks ) == 0
    calls = []
    feat.store( lambda : calls.append( 1 ) )
    feat.store( lambda : calls.append( 2 ) )
    assert len( sbldpy._callbacks ) == 2
    feat.call_stored()
    feat.call_stored()
    assert calls == [ 1, 2, 1, 2 ]
    feat.clear_stored()
    assert len( sbldpy._callbacks ) == 0
    #Callbacks are released if a later argument can not be converted:
    expect( TypeError, feat.integrate, lambda x : x, 'notanint' )
    assert len( sbldpy._callbacks ) == 0
    #Reentrant calls:
    assert feat.cbstr( lambda s, n : feat.greet( s ) + feat.cbstr( lambda s2, n2 : feat.greet( s2 * n2 ) ) ) \
        == 'Hello xHello xxx!!'
    def inner( x ):
        return feat.integrate( lambda y : x * y, n = 10 )
    assert abs( feat.integrate( inner, n = 10 ) - 0.25 ) < 1e-12
    e = expect( KeyError, feat.integrate, lambda x : feat.integrate( bad_callback, 10 ), 10 )
    assert 'inside callback' in str( e )
    #Several threads (the GIL is released during calls):
    res = {}
    errors = []
    def work( i ):
        try:
            res[i] = feat.integrate( lambda x : x * i, n = 2000 )
            expect( KeyError, feat.integrate, bad_callback, 10 )
        except BaseException as e:
            errors.append( e )
    threads = [ threading.Thread( target = work, args = ( i, ) ) for i in range( 8 ) ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    assert sorted( round( v, 6 ) for v in res.values() ) == [ i * 0.5 for i in range( 8 ) ]
    #A stored callback remains when the module is shut down at exit:
    feat.store( lambda : None )

if __name__ == '__main__':
    for section in sys.argv[1:]:
        globals()[ 'check_' + section ]()
        print( 'check %s OK'%section )
