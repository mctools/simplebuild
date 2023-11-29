# To keep things clean and allow for future migrations to different cfg systems,
# this file should be the ONLY place we query environment variables!!

def _query(n, *, boolean=False):
    import os
    _ = os.environ.get(n)
    if boolean:
        return (_ or '').lower() in ['true', 'on', 'yes', '1']
    return _

def _build_cfg():
    from .cfglocate import locate_master_cfg_file
    from .cfgbuilder import CfgBuilder
    from .singlecfg import SingleCfg
    from .pkgfilter import PkgFilter
    master_cfg_file = locate_master_cfg_file()

    if not master_cfg_file or not master_cfg_file.is_file():
        from . import error
        error.error('In order to continue, please step into a directory'
                    ' tree with a simplebuild.cfg file at its root.')

    assert master_cfg_file.is_file()

    master_cfg = SingleCfg.create_from_toml_file( master_cfg_file )
    cfg = CfgBuilder( master_cfg, master_cfg_file )
    pkgfilterobj = PkgFilter( cfg.build_pkg_filter )

    cachedir_postfix = ( '' if master_cfg.build_mode=='release'
                           else f'_{master_cfg.build_mode}' )

    import shlex
    _cmake_args = shlex.split( _query('CMAKE_ARGS') or '' )

    if master_cfg.build_mode=='release':
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Release')
    else:
        assert master_cfg.build_mode=='debug'
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Debug')
    _build_mode_summary_string = master_cfg.build_mode.capitalize()

    class EnvCfg:

        #These are the basic ones:
        build_dir_resolved = cfg.build_cachedir / f'bld{cachedir_postfix}'
        install_dir_resolved = cfg.build_cachedir / f'install{cachedir_postfix}'

        projects_dir = master_cfg.project_pkg_root #FIXME: Is this ok?
        extra_pkg_path = ':'.join(str(e) for e in cfg.pkg_path)#fixme: keep at Path objects.
        extra_pkg_path_list = cfg.pkg_path#New style!
        enable_projects_pkg_selection_flag = False#fixme: we could allow this?
        pkg_filter = pkgfilterobj#New style!

        #These are used in the context of conda installs:
        conda_prefix =  _query('CONDA_PREFIX')
        cmake_args =  _cmake_args

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

        build_mode_summary_string = _build_mode_summary_string

    return EnvCfg()

var = _build_cfg()
