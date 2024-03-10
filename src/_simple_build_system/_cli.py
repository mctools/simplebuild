
def _handle_env_setup( args ):
    def _check_nargs():
        if len(args)>1:
            raise SystemExit('Error: Do not use --env-setup or'
                             ' --env-unsetup with other arguments!')
    if any(a.startswith('--env-u') for a in args):
        _check_nargs()
        #Enable --env-unsetup usage, even outside a simplebuild project:
        from . import io as _io
        _io.make_quiet()
        from .envsetup import emit_env_unsetup
        emit_env_unsetup()
        raise SystemExit
    if any(a.startswith('--env-s') for a in args):
        _check_nargs()
        #Short-circuit to efficiently enable --env-setup call:
        from . import io as _io
        _io.make_quiet()
        from .envsetup import emit_envsetup
        emit_envsetup()
        raise SystemExit

def main( prevent_env_setup_msg = False ):
    import sys
    _args = sys.argv[1:]
    if any( e.startswith('--env-') for e in _args ):
        #Special short-circuit for --env-[un]setup:
        _handle_env_setup(_args)
    from . import frontend
    frontend.simplebuild_main( prevent_env_setup_msg = prevent_env_setup_msg )

def unwrapped_main():
    #For the unwrapped_simplebuild entry point, presumably only called from a
    #shell function which might provide a special --env-setup-silent-fail.
    import sys
    if len(sys.argv)==2 and sys.argv[1]=='--env-setup-silent-fail':
        #Quietly check if we are in a simplebuild project, and abort if not.
        from .cfglocate import locate_main_cfg_file
        mf = locate_main_cfg_file()
        if mf and mf.is_file():
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
    request_help = ( len(args)==1 and args[0] in ('-h','--help') )
    if request_help or not args:
        print("""Usage:

sbenv <program> [args]

Runs <program> within the simplebuild runtime environment. Note that if you wish
to make sure the codebase has been built first (with simplebuild) you should use
sbrun rather than sbenv.
""")
        raise SystemExit(0 if request_help else 111)
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
    request_help = ( len(args)==1 and args[0] in ('-h','--help') )
    if request_help or not args:
        print("""Usage:

sbrun <program> [args]

Runs the simplebuild 'sb' command (quietly) and if it finishes successfully,
then proceeds to launch <program> within the simplebuild runtime environment.
""")
        raise SystemExit(0 if request_help else 111)
        return
    from . import frontend
    frontend.simplebuild_main( argv = ['sb',
                                       '--quiet'],
                               prevent_env_setup_msg = True )
    sbenv_main( args )

if __name__=='__main__':
    main()
