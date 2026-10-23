def _handle_env_setup( args ):
    if any(a.startswith('--env-u') for a in args):
        if len(args)>1:
            raise SystemExit('Error: Do not use --env-unsetup with'
                             ' other arguments!')
        #Enable --env-unsetup usage, even outside a simplebuild project:
        from . import io as _io
        _io.make_quiet()
        from .envsetup import emit_env_unsetup
        emit_env_unsetup()
        raise SystemExit
    if any(a.startswith('--env-s') for a in args):
        #Short-circuit to efficiently enable --env-setup call. Only the flags
        #selecting the build variant can be combined with --env-setup:
        from . import variant
        others = [a for a in args if not a.startswith('--env-s')]
        res = variant.fast_parse_leading_flags( others + ['dummy'] )
        if len(others)+1 == len(args) and res and res[1] == ['dummy']:
            variant.select( res[0] )
        else:
            raise SystemExit('Error: Do not use --env-setup with other'
                             ' arguments than -d, -r, -g, or -x!')
        from . import io as _io
        _io.make_quiet()
        from .envsetup import emit_envsetup
        emit_envsetup()
        raise SystemExit

def _exit_after_interrupt( quiet = False ):
    #Exit cleanly (and without a traceback) after a keyboard interrupt (CTRL-C):
    import sys
    sys.stdout.flush()
    if not quiet:
        from . import io as _io
        _io.print('Interrupted by user (CTRL-C).')
    raise SystemExit(130)

def main( prevent_env_setup_msg = False ):
    import sys
    _args = sys.argv[1:]
    if any( e.startswith('--env-') for e in _args ):
        #Special short-circuit for --env-[un]setup:
        _handle_env_setup(_args)
    from . import frontend
    try:
        frontend.simplebuild_main( prevent_env_setup_msg = prevent_env_setup_msg )
    except KeyboardInterrupt:
        _exit_after_interrupt()
    except SystemExit as e:
        #Unless in quiet mode, error messages are printed on stdout (rather
        #than stderr), so they appear in the right place when the output is
        #redirected to a file. In quiet mode, only errors are printed, on
        #stderr:
        from . import io as _io
        if isinstance( e.code, str ) and not _io.is_quiet():
            _io.print_no_prefix( e.code )
            sys.stdout.flush()
            raise SystemExit(1)
        raise

def _env_setup_after_build( sb_args ):
    #Emit env setup code after a build performed by the sb shell function (see
    #shellrc_snippet.sh), for the build variant selected by the flags in
    #sb_args (the arguments of that build). Since the output will be eval'ed by
    #the shell, we must not emit anything except the env setup code. Thus we
    #quietly abort if not in a simplebuild project or if sb_args are not valid
    #(e.g. "sb -h").
    from .cfglocate import locate_main_cfg_file
    mf = locate_main_cfg_file()
    if not mf or not mf.is_file():
        return
    import contextlib
    import os
    from .parse_args import parse_args
    try:
        #NB: No parenthesised context managers, since we support python 3.9:
        with open(os.devnull,'w') as devnull, \
             contextlib.redirect_stdout(devnull), \
             contextlib.redirect_stderr(devnull):
            opt = parse_args( argv = ['sb'] + sb_args )
    except SystemExit:
        return
    from . import variant
    variant.select( variant.from_argparse_result( opt ) )
    from . import io as _io
    _io.make_quiet()
    from .envsetup import emit_envsetup
    emit_envsetup()

def _outdated_shell_function_error():
    #The sb shell function from simplebuild versions before the introduction
    #of build variant flags (-d, -r, -g, -x) invoked --env-setup-silent-fail
    #after each build, which would not respect such flags. Since the output of
    #this is eval'ed by the shell, we print nothing to stdout:
    import pathlib
    snippet = ( pathlib.Path(__file__).parent / 'data' / 'resources'
                / 'shellrc_snippet.sh' ).read_text()
    from .error import error
    error('Your shell is using an outdated version of the "sb" shell'
          ' function (usually\ndefined in a file like ~/.bashrc or ~/.zshrc).'
          ' Please replace it with the\nfollowing, and start a new shell:\n\n'
          + snippet )

def unwrapped_main():
    #For the unwrapped_simplebuild entry point, presumably only called from a
    #shell function which provides a special --env-setup-after-build flag in
    #order to setup the environment after a build.
    import sys
    if len(sys.argv)>=2:
        if sys.argv[1]=='--env-setup-after-build':
            _env_setup_after_build( sys.argv[2:] )
            raise SystemExit
        if len(sys.argv)==2 and sys.argv[1]=='--env-setup-silent-fail':
            _outdated_shell_function_error()
    sys.argv[0] = 'sb'
    main( prevent_env_setup_msg = True )

_sbenv_descr = """
Runs <program> within the simplebuild runtime environment. Note that if you wish
to make sure the codebase has been built first (with simplebuild) you should use
sbrun rather than sbenv.

The flags -d, -r, -g, and -x can be used to select the build variant, exactly as
for the sb command (see "sb --help"). They must be placed before <program>,
since all arguments after it are passed on to <program>.
"""

_sbrun_descr = """
Runs the simplebuild 'sb' command (quietly) and if it finishes successfully,
then proceeds to launch <program> within the simplebuild runtime environment.

The flags -d, -r, -g, and -x can be used to select the build variant, exactly as
for the sb command (see "sb --help"). They must be placed before <program>,
since all arguments after it are passed on to <program>.
"""

def _parse_launcher_args( progname, args, descr ):
    if not args:
        #Backwards compatible special case:
        print(f'Usage:\n\n{progname} [-d|-r|-g] [-x] <program> [args]\n'
              + descr)
        raise SystemExit(111)
    from .variant import parse_launcher_args
    return parse_launcher_args( progname, args, descr.strip() )

def _launch_in_env( program_and_args ):
    #NB: Variant must already have been selected.
    from . import io as _io
    _io.make_quiet()
    from .envsetup import create_install_env_clone
    run_env = create_install_env_clone()
    from .envcfg import var
    from .cachedirs import touch_last_used
    touch_last_used( var.build_dir_resolved, create_missing = False )
    from . import utils
    import shlex
    cmd = ' '.join(shlex.quote(e) for e in program_and_args)
    try:
        ec = utils.system(cmd,env=run_env)
    except KeyboardInterrupt:
        #The program was interrupted, which it presumably handled itself:
        _exit_after_interrupt( quiet = True )
    raise SystemExit(int(ec))

def sbenv_main( args = None ):
    if args is None:
        import sys
        args = sys.argv[1:]
    vflags, program_and_args = _parse_launcher_args( 'sbenv', args,
                                                     _sbenv_descr )
    from . import variant
    variant.select( vflags )
    _launch_in_env( program_and_args )

def sbrun_main():
    import sys
    vflags, program_and_args = _parse_launcher_args( 'sbrun', sys.argv[1:],
                                                     _sbrun_descr )
    from . import io as _io
    _io.make_quiet()
    sbargs = ['sb','--quiet']
    if vflags.mode:
        sbargs.append( vflags.mode_flag() )
    if vflags.ignore_extra_flags:
        sbargs.append( '-x' )
    from . import frontend
    try:
        frontend.simplebuild_main( argv = sbargs, prevent_env_setup_msg = True )
    except KeyboardInterrupt:
        _exit_after_interrupt( quiet = True )
    _launch_in_env( program_and_args )

if __name__=='__main__':
    main()
