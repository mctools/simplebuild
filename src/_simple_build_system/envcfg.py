# To keep things clean and allow for future migrations to different cfg systems,
# this file should be the ONLY place we query environment variables!!

def _query(n, *, boolean=False):
    import os
    _ = os.environ.get(n)
    if boolean:
        return (_ or '').lower() in ['true', 'on', 'yes', '1']
    return _

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
    cfg = CfgBuilder( main_cfg, main_cfg_file )
    pkgfilterobj = PkgFilter( cfg.build_pkg_filter )

    import shlex
    _cmake_args = shlex.split( _query('CMAKE_ARGS') or '' )

    if main_cfg.build_mode in ('release','reldbg'):
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Release')
        if main_cfg.build_mode == 'reldbg':
            #not just CMAKE_BUILD_TYPE=RelWithDebInfo since that changes other
            #flags as well.
            _cmake_args.append('-DSBLD_RELDBG_MODE=ON')
    else:
        assert main_cfg.build_mode=='debug'
        _cmake_args.append('-DCMAKE_BUILD_TYPE=Debug')
    _build_mode_summary_string = main_cfg.build_mode#.capitalize()

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
