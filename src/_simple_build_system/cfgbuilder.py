from .singlecfg import SingleCfg
from . import error
import pathlib

def load_builtin_cfgs():
    pd = pathlib.Path(__file__).absolute().parent / 'data'
    cfgs = [ ( pd / 'pkgs-core' / 'simplebuild.cfg' ).absolute().resolve(),
             ( pd / 'pkgs-core_val' / 'simplebuild.cfg' ).absolute().resolve() ]
    return [ ( p, SingleCfg.create_from_toml_file(p,ignore_build=True) ) for p in cfgs ]

class CfgBuilder:

    """Class which, based on an initial "main" simplebuild.cfg, can locate and
    extract other simplebuild cfg's, and provide a combined configuration object.

    The "build" section (build mode, ncpu, pkgfilter, etc.) is taken straight
    from the main config, while the other sections are based on a combination
    of data in the main_cfg and any cfg's of the dependencies.

    """

    def __init__(self, main_cfg : SingleCfg, main_cfg_file ):
        #Input:
        #Take build settings straight from main_cfg:
        from . import io as _io
        print_prefix = f'{_io.print_prefix}cfgbuilder:'
        self.__print = lambda *a,**kw: _io.print_no_prefix(print_prefix,*a,**kw)
        self.__is_verbose = _io.is_verbose
        self.__build_mode = main_cfg.build_mode
        #self.__build_njobs = main_cfg.build_njobs
        self.__build_cachedir = main_cfg.build_cachedir
        cachedir_postfix = ( '' if main_cfg.build_mode=='release'
                             else f'_{main_cfg.build_mode}' )
        self.__build_dir_resolved = ( main_cfg.build_cachedir
                                      / f'bld{cachedir_postfix}' )
        self.__install_dir_resolved = ( main_cfg.build_cachedir
                                        / f'install{cachedir_postfix}' )

        self.__build_pkg_filter = main_cfg.build_pkg_filter
        #self.__build_extdep_ignore = main_cfg.build_extdep_ignore

        #Build up everything else recursively, starting from the main_cfg:
        self.__pkg_path = []
        self.__extdep_path = []
        self.__env_paths = {}
        self.__used_cfg_files = set()#make sure we don't consider the same cfg-file twice
        self.__used_cfg_files.add( main_cfg_file )
        self.__available_unused_cfgs = []#only needed during build up
        self.__cfg_names_used = set()
        self.__cfg_names_missing = set([ main_cfg.bundle_name ])
        self.__dyngenscripts = []
        self.__use_cfg( main_cfg, is_top_level = True )

        for cfg_file, cfg in load_builtin_cfgs():
            #core/core-val bundles always available directly from core
            #installation, but we only add them if they were not added already
            #via a search_path entry (to facilitate development of core pkgs
            #directly from a git clone):
            if cfg.bundle_name in self.__cfg_names_missing:
                self.__print_verbose(f'Using built-in cfg: {cfg_file}')
                assert cfg_file not in self.__used_cfg_files
                self.__used_cfg_files.add( cfg_file )
                self.__use_cfg( cfg )

        if self.__cfg_names_missing:
            #Only consider python plugins if there is anything we did not find
            #already in the directly requested search paths (that way a dev
            #environment with everything checked out will be unaffected by what
            #plugins happen to be installed in the environment):
            self.__consider_python_plugins()
        if self.__cfg_names_missing:
            _p='", "'.join(self.__cfg_names_missing)
            _s = 's' if len(self.__cfg_names_missing)>2 else ''
            error.error('Could not find dependent bundles%s: "%s"'%(_s,_p))
        self.__pkg_path = tuple( self.__pkg_path )
        self.__extdep_path = tuple( self.__extdep_path )
        del self.__available_unused_cfgs
        if self.__dyngenscripts:
            self.__invoke_dynamic_generators()

    def __invoke_dynamic_generators( self ):
        from .io import print
        import sys
        import subprocess
        assert self.__dyngenscripts
        pyexec = sys.executable or 'python3'
        for bundle_name, script in self.__dyngenscripts:
            if not script.name.endswith('.py'):
                error.error('dynamic_generator script name must end in .py')
            descr = f' from {bundle_name}' if bundle_name else ''
            from .io import is_quiet
            is_quiet_val = is_quiet()
            if not is_quiet_val:
                print(f"Invoking {script}{descr}")
            rv = subprocess.run( [ pyexec, '-BI', script,
                                   str(self.__install_dir_resolved),
                                   str(self.__build_mode) ],
                                 capture_output = is_quiet_val )
            if rv.returncode!=0:
                error.error('dynamic_generator script invocation failed')

    def __print_verbose( self, *a,**kw ):
        if self.__is_verbose():
            self.__print( *a, **kw )

    @property
    def build_mode( self ):
        return self.__build_mode

    #@property
    #def build_njobs( self ):
    #    return self.__build_njobs

    @property
    def build_cachedir( self ):
        return self.__build_cachedir

    @property
    def build_dir_resolved( self ):
        return self.__build_dir_resolved

    @property
    def install_dir_resolved( self ):
        return self.__install_dir_resolved

    @property
    def build_pkg_filter( self ):
        return self.__build_pkg_filter

    #@property
    #def build_extdep_ignore( self ):
    #    return self.__build_extdep_ignore

    @property
    def pkg_path(self):
        return self.__pkg_path

    @property
    def env_paths(self):
        return self.__env_paths

    @property
    def extdep_path(self):
        return self.__extdep_path

    def __use_cfg( self, cfg : SingleCfg, is_top_level = False ):
        assert cfg.bundle_name in self.__cfg_names_missing
        _cfgname='main-' if is_top_level else ''
        self.__print_verbose(f'Using {_cfgname}cfg from {cfg._cfg_file}')
        self.__cfg_names_missing.remove( cfg.bundle_name )
        self.__cfg_names_used.add( cfg.bundle_name )
        if cfg.bundle_dynamic_generator:
            dyngenscript = cfg.bundle_dynamic_generator
            if not any(dyngenscript.samefile(s) for s in self.__dyngenscripts):
                self.__dyngenscripts.append( ( cfg.bundle_name, dyngenscript ) )

        #Add dependencies and cfgs available in search paths:
        for cfgname in cfg.depend_bundles:
            if cfgname not in self.__cfg_names_used:
                self.__cfg_names_missing.add( cfgname )
        for sp in cfg.depend_search_path:
            if not sp.exists():
                error.error
            assert sp.is_file()
            sp = sp.absolute()
            if sp in self.__used_cfg_files:
                continue
            self.__used_cfg_files.add( sp )
            depcfg = SingleCfg.create_from_toml_file(
                sp,
                ignore_build = not is_top_level
            )
            self.__available_unused_cfgs.append( depcfg )

        #Add actual pkg-dirs and env-path requests from cfg:
        if cfg.bundle_pkg_root not in self.__pkg_path:
            self.__pkg_path.append( cfg.bundle_pkg_root )
        if cfg.bundle_extdep_root and cfg.bundle_extdep_root not in self.__extdep_path:
            self.__extdep_path.append( cfg.bundle_extdep_root )
        for pathvar,contents in cfg.bundle_env_paths.items():
            if pathvar not in self.__env_paths:
                self.__env_paths[pathvar] = set()
            self.__env_paths[pathvar].update( contents )

        #Use cfgs we found as appropriate:
        self.__search_available_cfgs()

    def __search_available_cfgs( self ):
        if not self.__cfg_names_missing:
            return
        to_use_idx, to_use_cfg = set(), []
        for i,ucfg in enumerate(self.__available_unused_cfgs):
            if ucfg.bundle_name in self.__cfg_names_missing:
                to_use_cfg.append( ucfg )
                to_use_idx.add( i )
        if to_use_cfg:
            for i in sorted(to_use_idx,reverse=True):
                del self.__available_unused_cfgs[i]
            for ucfg in to_use_cfg:
                self.__use_cfg( ucfg )

    def __consider_python_plugins( self ):
        #First, find all possible python packages with plugins:
        own_pkg_name = pathlib.Path(__file__).parent.name
        import importlib
        import pkgutil
        possible_pyplugins = set(
            name
            for finder, name, ispkg
            in pkgutil.iter_modules()
            if ( name != own_pkg_name and
                 ( name.startswith('simplebuild_')
                   or name.startswith('_simplebuild_')
                  )
                )
        )

        #Load their cfgs:
        for name in sorted(possible_pyplugins):
            modname=f'{name}.simplebuild_bundle_list'
            self.__print_verbose(f'Trying python plugin module {modname}')
            try:
                mod = importlib.import_module(modname)
            except ModuleNotFoundError:
                self.__print_verbose(' -> skipping due to ModuleNotFoundError')
                continue
            if not hasattr( mod, 'simplebuild_bundle_list' ):
                self.__print_verbose(' -> skipping due to missing simplebuild_bundle_list function')
                continue
            srcdescr = 'Python module %s'%name
            for cfg_file in mod.simplebuild_bundle_list():
                if not cfg_file.is_absolute() or not cfg_file.is_file():
                    error.error(f'Non-absolute or non-existing cfg file path returned from {srcdescr}')
                #The .resolve() in the next line means that it is easier to work
                #with an on-disk clone of a repo which is otherwise providing
                #it's bundles after a pip install. If that clone is then "pip
                #install -e" (editable), then the resolve will go to the on-disk
                #clone rather than the symlinked file in the site-packages
                #area. The advantage is that newly added files in these repos
                #will still be picked up.
                cfg_file = cfg_file.absolute().resolve()
                if cfg_file in self.__used_cfg_files:
                    self.__print_verbose(f' -> skipping provided file already used: {cfg_file}')
                    continue#Already used
                self.__used_cfg_files.add( cfg_file )
                cfg = SingleCfg.create_from_toml_file( cfg_file, ignore_build = True )
                self.__available_unused_cfgs.append( cfg )

        #Use cfgs we found as appropriate:
        self.__search_available_cfgs()
