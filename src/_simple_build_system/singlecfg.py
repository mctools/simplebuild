import pathlib
import typing
import re
from . import error

_OptPath = typing.Union[pathlib.Path, None]# "pathlib.Path | None" needs py3.10+

class TOMLSchemaDecodeContext(typing.Protocol):
    @property
    def src_descr(self) -> str:
        return ''
    @property
    def default_dir(self) -> _OptPath:
        return None
    @property
    def item_name(self) -> str:
        return ''

def decode_list_of_search_paths( ctx : TOMLSchemaDecodeContext, item ):
    if not isinstance( item, list ):
        error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected list) in {ctx.src_descr}')
    res=[]
    for i,k in enumerate(item):
        if not isinstance(k,str) or not k:
            error.error(f'Invalid value of list entry #{i+1} in item {ctx.item_name} (expected non-empty string) in {ctx.src_descr}')
        p = pathlib.Path(k).expanduser()
        if not p.is_absolute():
            if ctx.default_dir is None:
                error.error(f'Invalid option "{item}" for item {ctx.item_name} (relative paths can only'
                            f' be used in a context where the "root" dir is apparent) in {ctx.src_descr}')
            p = ctx.default_dir / p
        if not p.exists():
            error.error(f'Non-existing path "{p}" in list entry #{i+1} in item {ctx.item_name} in {ctx.src_descr}')
        if p.is_file():
            p_redirect = p if p.name=='simplebuild_redirect.cfg' else None
            p_std = p if p_redirect is None else None
        if p.is_dir():
            #Unless the filename is specified directly, add the default name:
            p_std = ( p / 'simplebuild.cfg' )
            p_redirect = ( p / 'simplebuild_redirect.cfg' )
            p_std = None if not p_std.exists() else p_std
            p_redirect = None if not p_redirect.exists() else p_redirect
        if p_std is None and p_redirect is None:
            error.error(f'Missing file "{p}" in list entry #{i+1} in item {ctx.item_name} in {ctx.src_descr}')
        if p_std is not None and p_redirect is not None:
            error.error('Both simplebuild.cfg and simplebuild_redirect.cfg file exists in search_path directory'
                        f' "{p}" in list entry #{i+1} in item {ctx.item_name} in {ctx.src_descr} (specify'
                        ' the full path to one of the files to specify which one you are interested in using.')
        if p_std is not None:
            res.append(p_std.absolute().resolve())
        else:
            assert p_redirect is not None
            #Ok, load redirection file and expand:
            rd = RedirectionCfg( p_redirect )
            for e in rd.search_path:
                res.append( e )

    return tuple(res)

class DecodeContext:
    def __init__(self, srcdescr, default_dir):
        self.__srcdescr : str = srcdescr
        self.__item_name : str = ''
        self.__default_dir : str = default_dir
    def set_item_name( self, n ):
        self.__item_name = n
    @property
    def src_descr(self) -> str:
        return self.__srcdescr
    @property
    def default_dir(self) -> _OptPath:
        return self.__default_dir
    @property
    def item_name(self) -> str:
        assert self.__item_name
        return self.__item_name

class RedirectionCfg:
    def __init__( self, path : pathlib.Path ):
        try:
            textdata = path.read_text()
        except UnicodeDecodeError:
            error.error(f'Not a text-file: {path}')
        cfgdict = decode_toml_textdata_to_dict( textdata, path )
        if list(cfgdict.keys())!= ['special'] or list(cfgdict['special'].keys())!= ['redirect_search_path']:
            error.error(f'Invalid format of redirection cfg file at {path}')
        ctx = DecodeContext( str(path), path.parent )
        ctx.set_item_name('redirect_search_path')
        self.__sp = decode_list_of_search_paths( ctx,
                                                 cfgdict['special']['redirect_search_path'] )
    @property
    def search_path( self ):
        return self.__sp

class SingleCfg:

    """Class which contains decoded configuration from a single source (a
    simplebuild.cfg file, a python module, etc.)."""

    @classmethod
    def create_from_toml_file( cls, path : pathlib.Path, ignore_build : bool = False ):
        try:
            textdata = path.read_text()
        except UnicodeDecodeError:
            error.error(f'Not a text-file: {path}')
        cfgdict = decode_toml_textdata_to_dict( textdata, path )
        return cls.__create_from_cfgdict( cfgdict, str(path), path.parent, ignore_build = ignore_build )

    @classmethod
    def __create_from_cfgdict( cls, cfgdict : dict, cfg_file : pathlib.Path, default_dir = None, ignore_build : bool = False ):
        o = cls.__create_empty()
        decode_with_schema_and_apply_result_to_obj( cfgdict, o,
                                                    defaultdir = default_dir,
                                                    cfg_file = cfg_file,
                                                    ignore_build = ignore_build )

        if o.project_name != 'core' and 'core' not in o.depend_projects:
            #Always add the core project as a dependency:
            o.depend_projects = list(e for e in o.depend_projects) + ['core']

        o._is_locked = True
        return o

    def __setattr__(self,name,*args,**kwargs):
        if getattr(self,'_is_locked',False):
            error.error(f'Trying to set attribute "{name}" of locked SingleCfg object.')
        object.__setattr__(self,name,*args,**kwargs)

    @classmethod
    def __create_empty( cls ):
        return cls( _private_construct_key = cls.__construct_key )

    __construct_key = id('dummy')#cheap "random" secret integer
    def __init__(self, *, _private_construct_key ):
        self._is_locked = False
        if _private_construct_key != self.__construct_key:
            raise TypeError("Direct initialisation disallowed")

#######################################################################################################

_cache_tomllib = [None]
def import_tomllib():
    if _cache_tomllib[0] is None:
        try:
            import tomllib
        except ModuleNotFoundError:
            try:
                import tomli as tomllib
            except ModuleNotFoundError:
                raise SystemExit('Required toml functionality is not found. Either use '
                                 'python 3.11+ or install tomli'
                                 ' ("conda install -c conda-forge tomli" or "pip install tomli") ')
        _cache_tomllib[0] = tomllib
    return _cache_tomllib[0]

_reexp_valid_identifier = r'^[A-Za-z][A-Za-z0-9_]*$'
_reobj_valid_identifier = re.compile(_reexp_valid_identifier)
def _is_valid_identifier( s ):
    return s and isinstance(s,str) and _reobj_valid_identifier.search(s) is not None

_reexp_valid_lowercase_identifier = r'^[a-z][a-z0-9_]*$'
_reobj_valid_lowercase_identifier = re.compile(_reexp_valid_identifier)
def _is_valid_lowercase_identifier( s ):
    return s and isinstance(s,str) and _reobj_valid_lowercase_identifier.search(s) is not None

is_valid_bundle_name = _is_valid_lowercase_identifier


def _generate_toml_schema():

    def decode_nonempty_str( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance(item,str) or not str:
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected non-empty string) in {ctx.src_descr}')
        return item

    def decode_valid_identifier_string( ctx : TOMLSchemaDecodeContext, item ):
        if not _is_valid_identifier(item):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected string matching {_reexp_valid_identifier}) in {ctx.src_descr}')
        return item

    def decode_valid_lowercase_identifier_string( ctx : TOMLSchemaDecodeContext, item ):
        if not _is_valid_lowercase_identifier(item):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected string matching {_reexp_valid_lowercase_identifier}) in {ctx.src_descr}')
        return item

    def decode_is_bool( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance( item, bool ):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected boolean "true" or "false") in {ctx.src_descr}')
        return item

    def decode_is_list_of_valid_identifier_string( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance( item, list ):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected list) in {ctx.src_descr}')
        for i,k in enumerate(item):
            if not _is_valid_identifier(k):
                error.error(f'Invalid value of list entry #{i+1} in item {ctx.item_name} (expected string matching {_reexp_valid_identifier}) in {ctx.src_descr}')
        return tuple(item)

    def decode_is_list_of_valid_lowercase_identifier_string( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance( item, list ):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected list) in {ctx.src_descr}')
        for i,k in enumerate(item):
            if not _is_valid_lowercase_identifier(k):
                error.error(f'Invalid value of list entry #{i+1} in item {ctx.item_name} (expected string matching {_reexp_valid_lowercase_identifier}) in {ctx.src_descr}')
        return tuple(item)

    def decode_is_env_paths( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance( item, list ):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected list) in {ctx.src_descr}')
        res = {}
        for idx,e in enumerate(item):
            parts = list(x.strip() for x in e.split(':<install>/') if x.strip())
            if not len(parts)>=2:
                error.error(f'Invalid value "{e}" for list entry #{idx+1} in item {ctx.item_name} (expected format like "VARNAME:<install>/SUBDIRNAME" but got "{e}") in {ctx.src_descr}')
            varname, install_subdirnames = parts[0],parts[1:]
            if varname not in res:
                res[varname] = set()
            res[varname].update(install_subdirnames)
        return res

    def decode_is_list_of_nonempty_str( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance( item, list ):
            error.error(f'Invalid value "{item}" for item {ctx.item_name} (expected list) in {ctx.src_descr}')
        for i,k in enumerate(item):
            if not isinstance(k,str) or not k:
                error.error(f'Invalid value of list entry #{i+1} in item {ctx.item_name} (expected non-empty string) in {ctx.src_descr}')
        return tuple(item)

    def decode_str_enum( ctx : TOMLSchemaDecodeContext, item, optionlist ):
        item = decode_nonempty_str( ctx, item )
        if item not in optionlist:
            error.error(f'Invalid option "{item}" for item {ctx.item_name} (must be one of {",".join(optionlist)}) in {ctx.src_descr}')
        return item

    def decode_nonneg_int( ctx : TOMLSchemaDecodeContext, item ):
        if not isinstance(item,int):
            error.error(f'Invalid option "{item}" for item {ctx.item_name} (must be a non-negative integer) in {ctx.src_descr}')
        return item

    def decode_dir( ctx : TOMLSchemaDecodeContext, item ):
        if isinstance( item, pathlib.Path ):
            #special case (likely no longer needed, for sources which already provides Path's rather than str's)
            p = item
            item = str(item)
        else:
            item = decode_nonempty_str( ctx, item )
            p = pathlib.Path(item).expanduser()
        if not p.is_absolute():
            if ctx.default_dir is None:
                error.error(f'Invalid option "{item}" for item {ctx.item_name} (relative paths can only'
                            f' be used in a context where the "root" dir is apparent) in {ctx.src_descr}')
            p = ctx.default_dir / p
        return p.absolute().resolve()

    return dict( project   = dict( name        = (decode_valid_lowercase_identifier_string,None),
                                   pkg_root      = (decode_dir, '.'),
                                   env_paths   = (decode_is_env_paths,[]),
                                  ),
                 depend    = dict( projects     = (decode_is_list_of_valid_lowercase_identifier_string,[]),
                                   search_path = (decode_list_of_search_paths,[])
                                  ),
                 build     = dict( mode = ( lambda a,b : decode_str_enum(a,b,('debug','release')), 'release' ),
                                   njobs = (decode_nonneg_int, 0),
                                   cachedir = (decode_dir, './simplebuild_cache'),
                                   pkg_filter = (decode_is_list_of_nonempty_str,[]),
                                   extdep_ignore = (decode_is_list_of_valid_identifier_string,[]),
                                   cmake_flags = (decode_is_list_of_nonempty_str,[]),
                                   extra_cflags = (decode_is_list_of_nonempty_str,[]),
                                   extra_linkflags = (decode_is_list_of_nonempty_str,[]),
                                   relaxed_compilation = (decode_is_bool,False),
                                  ),
                )

_cache_toml_scheme = [None]
def get_toml_schema():
    if _cache_toml_scheme[0] is None:
        _cache_toml_scheme[0] = _generate_toml_schema()
    return _cache_toml_scheme[0]

def read_text_file( f ):
    try:
        data = f.read_text()
    except UnicodeDecodeError:
        error.error(f'Not a text-file: {f}')
    return data

def decode_toml_textdata_to_dict( textdata : str, path = None ):
    tomllib = import_tomllib()
    descr = path or 'TOML data'
    try:
        cfg = tomllib.loads(textdata)
    except tomllib.TOMLDecodeError as e:
        error.error(f'Syntax error in {descr}: {e}')
    #if not cfg:
    #    error.error(f'No data defined in {descr}. If this is intentional, at least put a single line with the contents "[project]".')
    return cfg

def decode_with_schema_and_apply_result_to_obj( cfg : dict,
                                                targetobj : SingleCfg,
                                                defaultdir,
                                                cfg_file : pathlib.Path,
                                                ignore_build : bool ):
    schema = get_toml_schema()

    ctx = DecodeContext( str(cfg_file), defaultdir )

    #Validate+decode+apply values:
    for section, sectiondata in cfg.items():
        if ignore_build and section=='build':
            continue
        schemadata = schema.get(section)
        #forward compatibility: ignore unknown sections and keys
        if not schemadata:
            error.warn(f'Ignoring unknown simplebuild.cfg section "{section}" of {ctx.src_descr}.')
            continue
        for k,v in sectiondata.items():
            _ = schemadata.get(k)
            if _ is None:
                error.warn(f'Ignoring unknown simplebuild.cfg entry name "{k}" in section "{section}" of {ctx.src_descr}.')
                continue
            decodefct, defval = _
            ctx.set_item_name(f'{section}.{k}')
            v = decodefct(ctx,v)
            setattr( targetobj, f'{section}_{k}', v )
    #Apply default values:
    for sectionname, sectiondata in schema.items():
        if ignore_build and sectionname=='build':
            continue
        for k,(decodefct,defval) in sectiondata.items():
            attrname=f'{sectionname}_{k}'
            if not hasattr(targetobj,attrname):
                ctx.set_item_name(f'DEFAULT::{sectionname}.{k}')
                v = None if defval is None else decodefct(ctx,defval)
                setattr( targetobj,attrname, v )

    setattr(targetobj, '_cfg_file', cfg_file )


    return cfg
