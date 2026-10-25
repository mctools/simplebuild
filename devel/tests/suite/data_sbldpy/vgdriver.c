/* Loads an sbldpy module without Python and calls a few of its functions, for
   checking with valgrind that no memory is leaked (see test_valgrind in
   test_integration_sbldpy.py). Usage: vgdriver <module library> */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef const char * (*InfoFct)( void );
typedef int (*CallFct)( int, void **, void * );
typedef struct { const char * data; int64_t size; } StrData;

static int func_id( const char * info, const char * name )
{
  char pattern[256];
  snprintf( pattern, sizeof(pattern), "{\"name\":\"%s\",\"id\":", name );
  const char * pos = strstr( info, pattern );
  int res = -1;
  if ( !pos || sscanf( pos + strlen( pattern ), "%d", &res ) != 1 )
    return -1;
  return res;
}

int main( int argc, char ** argv )
{
  if ( argc != 2 )
    return 1;
  void * lib = dlopen( argv[1], RTLD_NOW | RTLD_LOCAL );
  if ( !lib ) {
    printf( "dlopen failed: %s\n", dlerror() );
    return 1;
  }
  InfoFct info_fct = (InfoFct)dlsym( lib, "sbldpy_module_info" );
  CallFct call_fct = (CallFct)dlsym( lib, "sbldpy_call" );
  const char * info = info_fct ? info_fct() : NULL;
  if ( !info || !call_fct )
    return 1;
  int id_strvalue = func_id( info, "strvalue" );
  int id_fail = func_id( info, "fail" );
  int id_make_counter = func_id( info, "make_counter" );
  const char * counter_info = strstr( info, "{\"name\":\"Counter\"" );
  const char * dtor_pos = counter_info ? strstr( counter_info, "\"dtor\":" ) : NULL;
  int id_counter_dtor = -1;
  if ( dtor_pos && sscanf( dtor_pos + 7, "%d", &id_counter_dtor ) != 1 )
    id_counter_dtor = -1;
  if ( id_strvalue < 0 || id_fail < 0 || id_make_counter < 0 || id_counter_dtor < 0 )
    return 1;
  /* String argument and result (kept alive in the result slot): */
  const char * text = "a string which is long enough to be heap allocated";
  StrData arg = { text, (int64_t)strlen( text ) };
  StrData res = { NULL, 0 };
  void * args[1] = { &arg };
  if ( call_fct( id_strvalue, args, &res ) != 0 || res.size != arg.size )
    return 1;
  /* Object created by C++ and deleted (as done when the Python object dies): */
  int64_t start = 5;
  void * cargs[1] = { &start };
  void * obj = NULL;
  if ( call_fct( id_make_counter, cargs, &obj ) != 0 || !obj )
    return 1;
  void * dargs[1] = { &obj };
  if ( call_fct( id_counter_dtor, dargs, NULL ) != 0 )
    return 1;
  /* Exceptions (setting the error message): */
  for ( int64_t which = 0; which < 7; ++which ) {
    double dres = 0.0;
    void * fargs[1] = { &which };
    if ( call_fct( id_fail, fargs, &dres ) == 0 )
      return 1;
  }
  printf( "vgdriver done\n" );
  return 0;
}
