# To keep things clean and allow for future migrations to different cfg systems,
# this file should be the ONLY place we query environment variables!!

def _query(n, *, boolean=False):
    import os
    _ = os.environ.get(n)
    if boolean:
        return (_ or '').lower() in ['true', 'on', 'yes', '1']
    return _

cache_root_envvar = 'SIMPLEBUILD_CACHE_ROOT'
cache_root_force_prefix = 'force::'

def cache_root_dirname( main_cfg_file, bundle_name ):
    """Name of the cache directory of a bundle, when placed in the directory
    given by the SIMPLEBUILD_CACHE_ROOT environment variable. It contains a hash
    of the full path to the main simplebuild.cfg file, so each checkout of a
    bundle gets its own cache directory."""
    import re
    import hashlib
    p = str( main_cfg_file.absolute().resolve() )
    h = hashlib.sha256( p.encode( 'utf-8', errors = 'surrogateescape' ) ).hexdigest()[:12]
    name = bundle_name or main_cfg_file.absolute().resolve().parent.name
    name = re.sub( '[^A-Za-z0-9_.-]', '_', name or '' )[:40] or 'unnamed'
    return f'sb_{name}_{h}'

def _decode_cache_root( main_cfg, main_cfg_file ):
    """Returns the cache directory due to the SIMPLEBUILD_CACHE_ROOT
    environment variable, or None if not applicable. Unless the value has a
    "force::" prefix, it only applies when the cachedir is not specified in the
    simplebuild.cfg file."""
    import pathlib
    from . import error
    v = ( _query( cache_root_envvar ) or '' ).strip()
    if not v:
        return None
    force = v.startswith( cache_root_force_prefix )
    if force:
        v = v[len(cache_root_force_prefix):].strip()
        if not v:
            error.error(f'No directory specified after "{cache_root_force_prefix}"'
                        f' in the {cache_root_envvar} environment variable.')
    if not force and 'build_cachedir' not in main_cfg.defaulted_items:
        return None
    root = pathlib.Path( v ).expanduser()
    if not root.is_absolute():
        error.error(f'The {cache_root_envvar} environment variable must be set'
                    f' to an absolute path (got "{v}").')
    if root.exists() and not root.is_dir():
        error.error(f'The {cache_root_envvar} environment variable does not'
                    f' point to a directory: {root}')
    return root.absolute() / cache_root_dirname( main_cfg_file,
                                                 main_cfg.bundle_name )

def _build_cfg():
    from .cfglocate import locate_main_cfg_file
    from .cfgbuilder import CfgBuilder
    from .singlecfg import SingleCfg
    from .pkgfilter import PkgFilter
    main_cfg_file = locate_main_cfg_file()

    if not main_cfg_file or not main_cfg_file.is_file():
        from . import error
        error.error('In order to continue, please step into a directory'
                    ' tree with a simplebuild.cfg file at its root.')

    assert main_cfg_file.is_file()

    main_cfg = SingleCfg.create_from_toml_file( main_cfg_file )

    #Combine with the variant selected on the command line (see variant.py):
    from . import variant
    vflags = variant.selected()
    build_mode = vflags.mode or main_cfg.build_mode
    if vflags.ignore_extra_flags:
        extra_cflags, extra_ldflags = tuple(), tuple()
    else:
        extra_cflags = main_cfg.build_extra_cflags
        extra_ldflags = main_cfg.build_extra_ldflags
    cachedir_suffix = variant.cachedir_suffix( build_mode,
                                               extra_cflags,
                                               extra_ldflags )

    _cachedir_from_env = _decode_cache_root( main_cfg, main_cfg_file )
    _cachedir = _cachedir_from_env or main_cfg.build_cachedir

    cfg = CfgBuilder( main_cfg, main_cfg_file,
                      build_mode = build_mode,
                      cachedir = _cachedir,
                      cachedir_suffix = cachedir_suffix )
    pkgfilterobj = PkgFilter( cfg.build_pkg_filter )

    import shlex
    _cmake_args = shlex.split( _query('CMAKE_ARGS') or '' )

    if build_mode in ('release','reldbg'):
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Release')
        if build_mode == 'reldbg':
            #not just CMAKE_BUILD_TYPE=RelWithDebInfo since that changes other
            #flags as well.
            _cmake_args.append('-DSBLD_RELDBG_MODE=ON')
    else:
        assert build_mode=='debug'
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Debug')

    _build_mode_summary_string = build_mode
    if build_mode != main_cfg.build_mode:
        _build_mode_summary_string += f' (due to {vflags.mode_flag()})'

    #Extra flags from the [build] section. These are kept separate from
    #_cmake_args, since changes to them must trigger a reconfiguration:
    _cfg_cmake_defines = []
    if extra_cflags:
        _ = ' '.join(extra_cflags)
        _cfg_cmake_defines.append(f'SBLD_CFG_EXTRA_CFLAGS={_}')
    if extra_ldflags:
        _ = ' '.join(extra_ldflags)
        _cfg_cmake_defines.append(f'SBLD_CFG_EXTRA_LDFLAGS={_}')

    _build_mode, _extra_cflags, _extra_ldflags = ( build_mode, extra_cflags,
                                                   extra_ldflags )

    #For the summary and warnings (None means no line in the summary):
    if extra_cflags or extra_ldflags:
        _extra_flags_summary_string = variant.extra_flags_description(
            extra_cflags, extra_ldflags )
    elif vflags.ignore_extra_flags:
        _extra_flags_summary_string = '<ignored due to -x>'
    else:
        _extra_flags_summary_string = None

    class EnvCfg:

        #These are the basic ones:
        build_dir_resolved = cfg.build_dir_resolved
        install_dir_resolved = cfg.install_dir_resolved

        main_bundle_pkg_root = main_cfg.bundle_pkg_root #FIXME: Is this ok?
        extra_pkg_path = ':'.join(str(e) for e in cfg.pkg_path)#fixme: keep at Path objects.
        extra_pkg_path_list = cfg.pkg_path#New style!
        extra_extdep_path = cfg.extdep_path or tuple([])
        pkg_filter = pkgfilterobj#New style!

        #These are used in the context of conda installs:
        conda_prefix =  _query('CONDA_PREFIX')
        cmake_args =  _cmake_args
        cfg_cmake_defines = _cfg_cmake_defines

        #These are most likely almost never used by anyone (thus keeping as env
        #vars for now!):
        color_fix_code = _query('SIMPLEBUILD_COLOR_FIX')
        allow_sys_dev =  _query('SIMPLEBUILD_ALLOWSYSDEV',boolean=True)

        # NOTE: backend.py also checks environment variables to check if
        # something changed needing an automatic cmake reconf. We provide a good
        # base list here:

        reconf_env_vars = [
            #All of the above except SIMPLEBUILD_ALLOWSYSDEV:
            'PATH','SIMPLEBUILD_COLOR_FIX','CONDA_PREFIX','CMAKE_ARGS','PYTHONPATH',
            #Also this one of course:
            'SIMPLEBUILD_CFG',
        ]

        env_paths = cfg.env_paths

        build_mode = _build_mode
        build_mode_summary_string = _build_mode_summary_string
        build_max_cachedirs = main_cfg.build_max_cachedirs
        build_cachedir = _cachedir
        #Whether the cache dir is placed due to SIMPLEBUILD_CACHE_ROOT:
        build_cachedir_from_env = _cachedir_from_env is not None
        main_cfg_file_resolved = main_cfg_file.absolute().resolve()
        extra_cflags = _extra_cflags
        extra_ldflags = _extra_ldflags
        extra_flags_summary_string = _extra_flags_summary_string

    return EnvCfg()

var = _build_cfg()
