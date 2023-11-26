
def main( prevent_env_setup_msg = False ):
    import sys
    if any( e.startswith('--env-') for e in sys.argv[1:] ):
        #Special short-circuit to efficiently enable standard --env-setup usage:
        if '--env-u' in sys.argv[1:]:
            #Enable --env-unsetup usage, even outside a simplebuild project:
            from . import io as _io
            _io.make_quiet()
            from .envsetup import emit_envunsetup
            emit_envunsetup()
            raise SystemExit
        if any(a.startswith('--env-s') for a in sys.argv[1:]):
            #Short-circuit to efficiently enable --env-setup call:
            from . import io as _io
            _io.make_quiet()
            from .envsetup import emit_envsetup
            emit_envsetup()
            raise SystemExit
    from . import frontend
    frontend.simplebuild_main( prevent_env_setup_msg = prevent_env_setup_msg )

def unwrapped_main():
    #For the unwrapped_simplebuild entry point, presumably only called from a
    #bash function taking care of the --env-setup-silent-fail.
    import sys
    if len(sys.argv)==2 and sys.argv[1]=='--env-setup-silent-fail':
        #Quietly check if we are in a simplebuild project, and abort if not.
        from .cfglocate import locate_master_cfg_file
        mf = locate_master_cfg_file()
        if mf and not mf.is_file():
            from . import io as _io
            _io.make_quiet()
            from .envsetup import emit_envsetup
            emit_envsetup()
        raise SystemExit

    sys.argv[0] = 'sb'
    main( prevent_env_setup_msg = True )

def sbenv_main( args = None):
    if args is None:
        import sys
        args = sys.argv[1:]
    if not args:
        print("""Usage:

sbenv <program> [args]

Runs <program> within the simplebuild runtime environment. Note that if you wish to
make sure the codebase has been built first (with simplebuild) you should use sbrun
rather than sbenv.
""")
        raise SystemExit(111)
        return
    from .envsetup import create_install_env_clone
    run_env = create_install_env_clone()
    from . import utils
    import shlex
    cmd = ' '.join(shlex.quote(e) for e in args)
    ec = utils.system(cmd,env=run_env)
    raise SystemExit(int(ec))

def sbrun_main():
    import sys
    args = sys.argv[1:]
    if not args:
        print("""Usage:

sbrun <program> [args]

Runs simplebuild (quietly) and if it finishes successfully, then proceeds to launch
<program> within the simplebuild runtime environment.
""")
        raise SystemExit(111)
        return
    from . import frontend
    frontend.simplebuild_main( argv = ['sb',
                                       '--quiet'],
                               prevent_env_setup_msg = True )
    sbenv_main( args )

if __name__=='__main__':
    main()
