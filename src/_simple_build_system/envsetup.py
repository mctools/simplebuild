def emit_envsetup( oldenv = None ):
    emit_env_dict( calculate_env_setup( oldenv ) )

def emit_env_unsetup( oldenv = None ):
    emit_env_dict( calculate_env_unsetup( oldenv ) )

def create_install_env_clone( env_dict = None ):
    if env_dict is None:
        import os
        env_dict = os.environ.copy()
    else:
        if hasattr( env_dict, 'copy' ):
            env_dict = env_dict.copy()
        else:
            import copy
            env_dict = copy.deepcopy(env_dict)
    env_dict_changes = calculate_env_setup()
    for k,v in env_dict_changes.items():
        if v is None:
            if k in env_dict:
                del env_dict[k]
        else:
            env_dict[k] = v
    return env_dict

def apply_envsetup_to_dict( current_env ):
    for k,v in calculate_env_setup( current_env ).items():
        if v is None:
            if k in current_env:
                del current_env[k]
        else:
            current_env[k] = v

def calculate_env_unsetup( oldenv = None ):
    #returns dict( var -> value ), with None values meaning the variable should
    #be unset.
    if oldenv is None:
        import os
        oldenv = os.environ
    env_dict = env_with_previous_pathvar_changes_undone( oldenv )
    for e in [ 'SBLD_INSTALL_PREFIX','SBLD_DATA_DIR','SBLD_LIB_DIR',
               'SBLD_TESTREF_DIR','SBLD_INCLUDE_DIR',
              ]:
        if e in env_dict or e in oldenv:
            env_dict[e] = None
    return env_dict

def verify_env_already_setup( oldenv = None ):
    #For unit test
    import os
    if oldenv is None:
        oldenv = os.environ
    e = calculate_env_setup()
    if e:
        print('ERROR: sbld environment not enabled. Requested changes are:')
        for k,v in sorted(e.items()):
            print(f'  {k}={v}')
        raise SystemExit(1)

def calculate_env_setup( oldenv = None ):
    #returns dict( var -> value ), with None values meaning the variable should
    #be unset.

    #First undo effects of any previous setup:
    if oldenv is None:
        import os
        oldenv = os.environ
    env_dict = calculate_env_unsetup( oldenv )

    #Figure out what we need in terms of installdir and env_path variables and
    #inject them with the correct values:
    from .envcfg import var
    instdir = var.install_dir_resolved
    fpcontent=[str(instdir)]
    for pathvar, inst_subdirs in sorted( var.env_paths.items() ):
        fpcontent.append( pathvar )
    assert not any(':' in e for e in fpcontent), "colons not allowed"

    #So inject our new variables:
    for pathvar, inst_subdirs in sorted( var.env_paths.items() ):
        prepend_entries = [ instdir / sd for sd in sorted(inst_subdirs) ]
        ed = env_dict if pathvar in env_dict else oldenv
        env_dict[pathvar] = modify_path_var( pathvar,
                                             env_dict = ed,
                                             blockpath = instdir,
                                             prepend_entries = prepend_entries )


    #Set relevant non-path vars:
    env_dict['_SIMPLEBUILD_CURRENT_ENV'] = ':'.join(str(e) for e in fpcontent)
    env_dict['SBLD_INSTALL_PREFIX']  = str(instdir)
    env_dict['SBLD_DATA_DIR']        = str(instdir/'data')
    env_dict['SBLD_LIB_DIR']         = str(instdir/'lib')
    env_dict['SBLD_TESTREF_DIR']     = str(instdir/'tests'/'testref')
    env_dict['SBLD_INCLUDE_DIR']     = str(instdir/'include')

    #Finally, remove those entries already at a correct value:
    for k in list(_ for _ in env_dict.keys()):
        v = env_dict[k]
        if v is None:
            if v not in oldenv:
                #already not there
                del env_dict[k]
            continue
        else:
            if oldenv.get(k)==v:
                #already at the right value:
                del env_dict[k]
    return env_dict

def env_with_previous_pathvar_changes_undone( oldenv ):
    assert oldenv is not None
    env = {}
    oldfp = oldenv.get('_SIMPLEBUILD_CURRENT_ENV')
    if oldfp:
        import pathlib
        _ = oldfp.split(':')
        old_instdir, old_pathvars = pathlib.Path(_[0]), set(_[1:])
        for pathvar in old_pathvars:
            env[pathvar] = modify_path_var(pathvar,env_dict=oldenv, blockpath=old_instdir)
    return env

def emit_env_dict( env_dict):
    import shlex
    from . import io as _io
    for k,v in sorted(env_dict.items()):
        if v is None:
            _io.raw_print_ignore_quiet(f'export {k}=')#always this first, since unset statement might be an error if not already set.
            _io.raw_print_ignore_quiet(f'unset {k}')
        else:
            _io.raw_print_ignore_quiet('export %s=%s'%(k,shlex.quote(str(v))))

def modify_path_var(varname,*,env_dict, blockpath = None, prepend_entries = None):
    """Removes all references to blockpath or its subpaths from a path variable,
    prepends any requested paths, and returns the result."""
    import pathlib
    assert env_dict is not None
    assert isinstance(blockpath,pathlib.Path)
    assert not blockpath.exists() or blockpath.is_dir()#if exists, must be dir
    if prepend_entries:
        res = prepend_entries[:]
    else:
        res = []
    from .utils import path_is_relative_to
    for e in env_dict.get(varname,'').split(':'):
        if e and ( blockpath is None or not path_is_relative_to( pathlib.Path(e), blockpath ) ):
            res.append(str(e))
    return ':'.join(unique_list(str(e) for e in res))

def unique_list(seq):
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]
