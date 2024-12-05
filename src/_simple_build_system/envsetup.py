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

def apply_envunsetup_to_dict( current_env ):
    for k,v in calculate_env_unsetup( current_env ).items():
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
    env_dict = undo_previous_pathvar_changes( oldenv )
    for e in [ 'SBLD_INSTALL_PREFIX','SBLD_DATA_DIR','SBLD_LIB_DIR',
               'SBLD_TESTREF_DIR','SBLD_INCLUDE_DIR',
               '_SIMPLEBUILD_CURRENT_ENV',
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

    #Figure out what we need in terms of installdir and env_path variables, so
    #we can inject them with the correct values:
    from .envcfg import var
    instdir = var.install_dir_resolved
    fpcontent=[str(instdir)]
    for pathvar, inst_subdirs in sorted( var.env_paths.items() ):
        if '%' in pathvar:
            from . import error
            error.error(f"Percent sign not allowed in variable name: {pathvar}")
        pathvar_orig_val = env_dict.get(pathvar,oldenv.get(pathvar))
        _prefix = '%' if pathvar_orig_val is None else ''
        fpcontent.append( _prefix + pathvar )
    if any(':' in e for e in fpcontent):
        from . import error
        error.error("Colons not allowed in cache dir or variable names")

    #So inject our new variables:
    for pathvar, entries_to_append in sorted( var.env_paths.items() ):
        prepend_entries = []
        prune_and_prepend_entries = []
        for e in sorted(entries_to_append):
            if e.startswith('<install>/'):
                prepend_entries.append(instdir / e[len('<install>/'):])
            else:
                prune_and_prepend_entries.append(e)

        ed = env_dict if pathvar in env_dict else oldenv
        env_dict[pathvar] = modify_path_var( pathvar,
                                             env_dict = ed,
                                             blockpath = instdir,
                                             prepend_entries = prepend_entries,
                                             prune_and_prepend_entries
                                             = prune_and_prepend_entries )


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
            if k not in oldenv:
                #already not there
                del env_dict[k]
            continue
        else:
            if oldenv.get(k)==v:
                #already at the right value:
                del env_dict[k]
    return env_dict

def undo_previous_pathvar_changes( oldenv ):
    assert oldenv is not None
    env = {}
    oldfp = oldenv.get('_SIMPLEBUILD_CURRENT_ENV')
    if not oldfp:
        return env
    import pathlib
    _ = oldfp.split(':')
    old_instdir, old_pathvars = pathlib.Path(_[0]), set(_[1:])
    for raw_pathvar in old_pathvars:
        if raw_pathvar.startswith('%'):
            was_absent = True
            pathvar = raw_pathvar[1:]
        else:
            was_absent = False
            pathvar = raw_pathvar
        newpv = modify_path_var( pathvar,
                                 env_dict=oldenv,
                                 blockpath=old_instdir)
        if newpv or not was_absent:
            env[pathvar] = newpv or ''
        elif pathvar in oldenv:
            env[pathvar] = None#this means unset
    return env

def emit_env_dict( env_dict):
    import shlex
    from . import io as _io
    for k,v in sorted(env_dict.items()):
        if v is None:
            #always export before unset, since unset statement might be an error
            #if not already set:
            _io.raw_print_ignore_quiet(f'export {k}=')
            _io.raw_print_ignore_quiet(f'unset {k}')
        else:
            _io.raw_print_ignore_quiet('export %s=%s'%(k,shlex.quote(str(v))))

def modify_path_var( varname, *,
                     env_dict,
                     blockpath = None,
                     prepend_entries = None,
                     prune_and_prepend_entries = None ):
    """Removes all references to blockpath or its subpaths from a path variable,
    prepends any requested paths, and returns the result."""
    import pathlib
    assert env_dict is not None
    assert isinstance(blockpath,pathlib.Path)
    existing = (env_dict.get(varname,'') or '').split(':')
    res = prepend_entries[:] if prepend_entries else []
    from .utils import path_is_relative_to
    for e in existing:
        if prune_and_prepend_entries and e in prune_and_prepend_entries:
            continue
        #NB: Keeping empty entries, to make setup->unsetup more likely to give
        #consistent results:
        if ( blockpath is None
             or not path_is_relative_to( pathlib.Path(e), blockpath ) ):
            res.append(str(e or ''))
    if prune_and_prepend_entries:
        res = prune_and_prepend_entries + res

    #NB: keeping duplicate entries, to make setup->unsetup more likely to
    #give consistent results:
    #return ':'.join(unique_list(str(e) for e in res))
    return ':'.join(str(e) for e in res)

#def unique_list(seq):
#    seen = set()
#    return [x for x in seq if not (x in seen or seen.add(x))]
