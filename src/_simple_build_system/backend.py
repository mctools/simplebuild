def perform_cfg( *,
                 select_filter=None,
                 force_reconf=False,
                 load_all_pkgs=False,
                 quiet=False,
                 verbose=False,
                 export_jsoncmds=False
                ):
    import os
    import sys
    import glob
    from . import extractenv
    from . import utils
    from . import loadpkgs
    from . import dirs
    from . import conf
    from . import error
    from . import mtime
    from . import envcfg
    import shlex
    import shutil
    from .io import print

    #Pre-inspect package directories, simply finding the package dirs for now (do it already to detect some errors early):
    all_pkgdirs = loadpkgs.find_pkg_dirs ( dirs.pkgsearchpath )

    #Inspect package tree and load the necessary pkg.info files, given the filters:
    pl = loadpkgs.PackageLoader( all_pkgdirs,
                                 select_filter,
                                 autodeps=conf.autodeps,
                                 load_all = load_all_pkgs )

    #Actual extdeps that might be used:
    actually_needed_extdeps = set()
    for p in pl.enabled_pkgs_iter():
        if p.enabled:
            actually_needed_extdeps.update(p.direct_deps_extnames)

    volatile_misc = envcfg.var.reconf_env_vars[:]

    #Inspect environment via cmake (caching the result of previous runs).

    def calc_current_reconf_environment( envdict ):
        return dict(
            install_dir = str(conf.install_dir()),
            build_dir = str(conf.build_dir()),
            env_hash = calc_environment_hash_dict(),
            command_paths = dict( (b,str(shutil.which(b)))
                                  for b in sorted(set(envdict['autoreconf']['bin_list'].split(';')))),
            environment_variables = dict( (e,os.environ.get(e))
                                          for e in sorted(set([*envdict['autoreconf']['env_list'].split(';'),*volatile_misc])) )
        )

    assert dirs.blddir.is_dir()
    assert ( dirs.blddir / '.sbbuilddir' ).exists()

    #TODO: This need to cache and retrigger on cmakeargs is a leftover from
    #ancient times. Should we simply remove it?
    cmakeargs = []

    envdict = None
    if not force_reconf and os.path.exists(dirs.envcache):
        #load from cache:
        envdict=utils.pkl_load(dirs.envcache)
        current_reconf_environment = calc_current_reconf_environment(envdict)
        #check if reconf has been triggered:
        if envdict['_cmakeargs'] != cmakeargs:
            if not quiet:
                print("Change in cmake variables detected => reinspecting environment")
            envdict=None
        elif envdict['_autoreconf_environment'] != current_reconf_environment:
            if not quiet:
                print("Change in environment detected => reinspecting via CMake")
                for e in calc_env_changes( envdict['_autoreconf_environment'],
                                           current_reconf_environment ):
                    print(f'  -> change: {e}')
            envdict=None
        elif len(actually_needed_extdeps - envdict['_actually_needed_extdeps']) > 0:
            if not quiet:
                print("Change in relevant extdeps detected => reinspecting via CMake")
            envdict=None

    #Make sure any change in reported python version triggers reconf (especially important during python2->python3 transision):
    pyversionstr = str(sys.version_info)
    if envdict and envdict.get('_pyversion',None)!=pyversionstr:
        if not quiet:
            print("Change in python environment detected => reinspecting via CMake")
            envdict=None

    from . import env
    _devel_testextract = os.environ.get('SBLD_DEVEL_TESTCMAKECFG_MODE')
    if _devel_testextract is not None:
        assert _devel_testextract in ('REUSE','INVOKECMAKE')

    if envdict:
        #Can reuse config:
        env.env=envdict
        if _devel_testextract is not None:
            assert _devel_testextract == 'REUSE'
    else:
        #must extract the hard way via cmake:
        if _devel_testextract is not None:
            assert _devel_testextract == 'INVOKECMAKE'

        envdict = extractenv.extractenv(
            cmakeargs = cmakeargs,
            actually_needed_extdeps = actually_needed_extdeps,
            quiet = quiet,
            verbose = verbose
        )
        if not envdict:
            utils.rm_f(dirs.envcache)
            error.error('Failure during cmake configuration')
        assert '_cmakeargs' not in envdict
        envdict['_cmakeargs']=cmakeargs
        assert '_actually_needed_extdeps' not in envdict
        envdict['_actually_needed_extdeps'] = actually_needed_extdeps
        assert '_autoreconf_environment' not in envdict
        envdict['_autoreconf_environment'] = calc_current_reconf_environment(envdict)
        envdict['_pyversion'] = pyversionstr
        envdict['system']['volatile'].update({ 'misc': {**dict((e,os.getenv(e)) for e in volatile_misc)} })
        utils.pkl_dump(envdict,dirs.envcache)
        #configuration fully extracted:
        env.env=envdict

        #(re)create any libs_to_symlink whenever extracting env via cmake:
        dirs.create_install_dir()
        linkdir = dirs.installdir / 'lib' / 'links'
        assert ( dirs.installdir / '.sbinstalldir' ).exists()
        shutil.rmtree( linkdir, ignore_errors=True)
        linkdir.mkdir(parents=True)
        for lib_to_symlink in env.env['system']['runtime']['libs_to_symlink']:
            #Symlink not only the given file, but also all other files in target
            #dir with same basename and pointing to same file (e.g. if libA.so
            #and libA.x.so both point to libA.so.x.y, then add symlinks for all
            #three names.
            lib_to_symlink=os.path.abspath(lib_to_symlink)
            bn,dn=os.path.basename(lib_to_symlink),os.path.dirname(lib_to_symlink)
            assert bn
            rp=os.path.realpath(lib_to_symlink)
            for f in glob.glob(os.path.join(dn,'%s*'%bn.split('.')[0])):
                if os.path.realpath(f)==rp:
                    os.symlink(rp,os.path.join(linkdir,os.path.basename(f)))

    #update extdep, language info and runtime files, to trigger makefile target rebuilds as necessary:
    #utils.mkdir_p(os.path.join(dirs.blddir,'extdeps'))
    utils.mkdir_p(dirs.blddir / 'extdeps')
    for extdep,info in envdict['extdeps'].items():
        utils.update_pkl_if_changed(info,dirs.blddir / 'extdeps' / extdep)

    utils.mkdir_p(dirs.blddir / 'langs')
    pybind11info = dict((k,v) for k,v in env.env['system']['general'].items() if k.startswith('pybind11'))
    for lang,info in envdict['system']['langs'].items():
        #add pybind11 info as well, to trigger rebuilds when needed.
        utils.update_pkl_if_changed( {'langinfo':info,'pybind11info':pybind11info},
                                     dirs.blddir / 'langs' / lang )

    #Possible external dependencies (based solely on available ExtDep_xxx.cmake files):
    possible_extdeps = set(envdict['extdeps'].keys())

    pl.check_no_forbidden_extdeps( possible_extdeps )


    #Gracefully disable packages based on missing external dependencies

    missing_extdeps = set(k for k,v in envdict['extdeps'].items() if not v['present'])
    missing_needed = set(missing_extdeps).intersection(pl.active_deps_extnames())

    if missing_needed:
        autodisable = True
        if autodisable:
            disabled = pl.disable_pkgs_with_extdeps(missing_extdeps)
            if disabled and not quiet:
                print(f'Disabled {len(disabled)} packages due '
                      'to missing external dependencies')
        else:
            #This is a leftover from when user absolutely wanted a particular
            #list of packages to be enabled. Perhaps we want to introduce such a
            #feature again?
            error.error('Selected packages have missing external '
                        'dependencies: "%s"'%'", "'.join(missing_needed))

    #Load old contents of global db:
    from . import db

    #Check if volatile parts of environment changed:
    volatile = env.env['system']['volatile']
    if db.db.get('volatile',None) != volatile:
        db.db['volatile']=volatile
        db.db['pkg2timestamp']={}#make all pkgs "dirty"

    #For each enabled package, put it in one of the following categories:
    #   a) Timestamps of package and all parents are unchanged
    #        => Do nothing for package (all info needed by other packages will be in the global
    #                                   db and the makefile for the package is still there).
    #   b) Timestamp of package unchanged but some parent had new timestamp.
    #        => Load pkg targets from pickle file (they still need to have setup() called).
    #   c) Timestamp of package itself changed.
    #        => Create targets for package from scratch.

    ts=db.db['pkg2timestamp']
    rd=db.db['pkg2reldir']

    #Force reconfig of pkg+clients if any direct extdep's changed!
    pkgdb_directextdeps = db.db['pkg2directextdeps']
    for p in pl.enabled_pkgs_iter():
        _e = pkgdb_directextdeps.get(p.name)
        if (_e or set()) != p.direct_deps_extnames:
            if verbose and _e is not None:
                print(f'Detected direct USEEXT changes in {p.name}')
            p.set_files_in_pkg_changed()
            #Not 100% sure we should do this here already, but it most likely
            #does not hurt:
            pkgdb_directextdeps[p.name] = set(e for e in p.direct_deps_extnames)

    #TODO: Implement the following for increased safety: We should first check
    #all packages if they moved reldirname. Those packages all have to be nuked
    #for safety, and if any packages are nuked, all must be reconfigured
    #(updating a symlink is not enough, as it could be that the compiler reads
    #the ultimate located of links and embeds the realpath in
    #executables). Moving packages should be rather rare, so best to be sure.

    for p in pl.enabled_pkgs_iter():
        mt=mtime.mtime_pkg(p)
        if not ( ts.get(p.name,None) == mt ):
            if verbose:
                print(f'Detected timestamp changes in {p.name}')
            p.set_files_in_pkg_changed()
            ts[p.name]=mt
        if rd.get(p.name,None)!=p.reldirname:
            if verbose:
                print(f'Detected location changes in {p.name}')
            p.set_files_in_pkg_changed()#added adhoc for safety
            #Make sure pkg symlink is in place (refering to the package in
            #symlinked location, potentially allows users to move pkgs around).
            lt=dirs.pkg_dir(p)
            if lt.is_dir() and not lt.is_symlink():
                assert utils.path_is_relative_to( lt, conf.build_dir() ) and ( conf.build_dir()/'.sbbuilddir' ).exists()
                shutil.rmtree( lt, ignore_errors=True)
            else:
                lt.parent.mkdir( parents = True, exist_ok = True )
                if lt.is_symlink():
                    lt.unlink()
                lt.symlink_to(p.dirname,target_is_directory=True)
            rd[p.name]=p.reldirname#ok to update immediately?

    def nuke_pkg(pkgname):
        if verbose:
            print(f'Completely wiping cache for {pkgname}')
        conf.uninstall_package(pkgname)
        utils.rm_rf(dirs.pkg_cache_dir(pkgname))
        utils.rm_rf(dirs.pkg_dir(pkgname))#remove link to pkg
        nt=shlex.quote(os.path.join(dirs.blddir,'named_targets',pkgname))
        utils.system('rm -f %s %s_*'%(nt,nt))#Fixme: this is potentially
                                             #clashy... we should not use single
                                             #underscores if they are allowed in
                                             #package names (see also fixmes in
                                             #conf.py).
        db.clear_pkg(pkgname)

    from . import target_builder
    any_enabled=False
    for p in pl.enabled_pkgs_iter():
        any_enabled=True
        if p.files_in_pkg_changed():
            #recreate pkg targets from scratch
            old_parts = db.db['pkg2parts'].get(p.name,set())
            db.clear_pkg(p.name)
            db.db['pkg2parts'][p.name]=set()
            err_txt,unclean_exception = None,None
            try:
                if verbose:
                    print(f'Recreating pkg targets for {p.name}')
                target_builder.create_pkg_targets(p)#this also dumps to pickle!
            except KeyboardInterrupt:
                err_txt = "Halted by user interrupt (CTRL-C)"
            except Exception as e:
                err_txt=str(e)
                if not err_txt:
                    err_txt='<unknown error>'
                if not isinstance(e,error.Error):
                    unclean_exception = e
            if err_txt:
                #Error! Nuke the offending package and mark ALL packages for
                #reconfig (since even the OK ones will not get makefiles updated).
                from . import col
                print()
                print(f'{col.bad}ERROR during configuration of package {p.name}:{col.end}')
                print()
                for e in err_txt.splitlines():
                    print(f'  {e}')
                print()
                nuke_pkg(p.name)
                db.db['pkg2timestamp']={}
                db.save_to_file()
                if unclean_exception:
                    #unknown exceptions need an ugly traceback so we can notice and try to avoid them in the future
                    error.print_traceback(unclean_exception)
                error.clean_exit(1)
            new_parts = db.db['pkg2parts'][p.name]
            disappeared_parts = old_parts.difference(new_parts)
            if disappeared_parts:
                conf.deinstall_parts(dirs.installdir,p.name,new_parts,disappeared_parts)
            #If we get here, package was updated OK:
            ts[p.name] = mtime.mtime_pkg(p)
            rd[p.name] = p.reldirname
            pkgdb_directextdeps[p.name] = set(e for e in p.direct_deps_extnames)
        elif p.any_parent_changed():
            #merely load targets from pickle!
            target_builder.create_pkg_targets_from_pickle(p)
        else:
            #nothing to be done
            pass

    if not any_enabled:
        error.error('No packages were enabled in the present configuration')

    #Global targets:
    global_targets = target_builder.create_global_targets()

    #Perform setup calls to targets:
    for p in pl.enabled_pkgs_iter():
        if hasattr(p,'targets'):
            for t in p.targets:
                assert not t.isglobal
                t.setup(pl.name2pkg[t.pkgname])

    for t in global_targets:
        assert t.isglobal
        t.setup(None)#has no associated pkg

    #Validate and collect:
    all_targets=[]
    for p in pl.enabled_pkgs_iter():
        if hasattr(p,'targets'):
            for t in p.targets:
                t.validate()
            all_targets += p.targets

    for t in global_targets:
        t.validate()
    all_targets+=global_targets

    export_jsoncmds_pkg = None
    export_jsoncmds_finalise = None
    if export_jsoncmds:
        from . import _export_jsoncmds
        export_jsoncmds_pkg      = _export_jsoncmds.export_pkg
        def export_jsoncmds_finalise():
            return _export_jsoncmds.finalise(export_jsoncmds)

    #setup makefiles:
    utils.mkdir_p(dirs.makefiledir)
    from . import makefile

    #the main makefile:
    enabled_pkgnames=list(p.name for p in pl.enabled_pkgs_iter())
    makefile.write_main(global_targets,enabled_pkgnames)


    #package makefiles:
    if export_jsoncmds_pkg:
        _makefile_var_map = makefile.get_makefile_global_vars()
    for p in pl.enabled_pkgs_iter():
        if hasattr(p,'targets'):#no targets means reuse old makefile
            makefile.write_pkg(p)
            if export_jsoncmds_pkg:
                export_jsoncmds_pkg(p,_makefile_var_map)

    if export_jsoncmds_finalise:
        export_jsoncmds_finalise()

    enabled_pkgnames=set(enabled_pkgnames)
    if 'enabled_pkgnames' in db.db:
        #Test if any pkgs got disabled compared to last time and remove it from install area:
        for disappeared_pkgname in db.db['enabled_pkgnames'].difference(enabled_pkgnames):
            if not quiet:
                print("Uninstalling package %s"%disappeared_pkgname)
            nuke_pkg(disappeared_pkgname)
    db.db['enabled_pkgnames'] = enabled_pkgnames

    #Save new state:
    db.save_to_file()


    dir_names = ('main_bundle_pkg_root','pkgsearchpath','blddir',
                 'installdir','testdir','envcache')
    dirdict = dict(((d, getattr(dirs, d)) for d in dir_names))

    #Update dynamic python module with information, if needed:
    cfgfile=dirs.blddir / 'cfg.py'
    cfg_picklefile=dirs.blddir / '_cfg_data.pkl'
    simplebuild_cfg_pkgs_dict = dict((p.name,p.info_as_dict()) for p in pl.pkgs)
    cfg_pickle_data = dict( cmakeargs = cmakeargs,
                            pkgs = simplebuild_cfg_pkgs_dict )
    utils.update_pkl_if_changed( cfg_pickle_data,
                                 cfg_picklefile )
    content='"""File automatically generated by simplebuild"""'
    content+=f"""
import pickle as _pkl
import pathlib as _pl

_pklfile = _pl.Path(__file__).parent / '{cfg_picklefile.name}'
with _pklfile.open('rb') as fh:
    _pkldata = _pkl.load(fh)
cmakeargs = _pkldata['cmakeargs']
pkgs = _pkldata['pkgs']
del _pklfile
del _pkldata

class Dirs:
"""
    for k,v in sorted(dirdict.items()):
      val = (f"_pl.Path({repr(str(v))}).absolute()" if not isinstance(v,list)
             else '['+','.join([f"_pl.Path({repr(str(el))})" for el in v])+']')
      content+=f"""
  @property
  def {k}(self):
    return {val}
"""
    content+="""
  @property
  def instdir(self):
    return _pl.Path(__file__).parent.parent.parent.absolute()

  @property
  def testrefdir(self):
    return self.instdir / 'tests' / 'testref'

  @property
  def datadir(self):
    return self.instdir / 'data'

  @property
  def libdir(self):
    return self.instdir / 'lib'

  @property
  def includedir(self):
    return self.instdir / 'include'

  @property
  def installprefix(self):
    return self.instdir

dirs = Dirs()
if __name__=="__main__":
  import pprint as pp
  pp.pprint(pkgs)
  pp.pprint({ p:getattr(dirs,p) for p in dir(dirs) if not p.startswith('_')})
"""
    try:
        current_content = cfgfile.read_text()
    except FileNotFoundError:
        current_content = None
    if current_content != content:
        cfgfile.write_text( content )

    return pl

def calc_env_changes( old, new ):
    if set(old.keys()) != set(new.keys()):
        yield 'autoreconf format change!'
        return
    dns = ('install_dir','build_dir')

    for dn in dns:
        if old[dn] != new[dn]:
            yield f'Directory changed: {dn}'
    for tn in [ tn for tn in sorted(old.keys()) if tn not in dns ]:
        old_tn, new_tn = old[tn], new[tn]
        ko, kn = set(old_tn.keys()), set(new_tn.keys())
        for k in kn|ko:
            vo, vn = old_tn[k], new_tn[k]
            if vo!=vn:
                vofmt = f'"{vo}"' if vo is not None else '<unset>'
                vnfmt = f'"{vn}"' if vn is not None else '<unset>'
                yield f'value of "{k}" ({tn}) changed from {vofmt} to {vnfmt}'
        for k in ko-kn:
            yield f'{tn} - no longer tracking "{k}"'
        for k in kn-ko:
            yield f'{tn} - now also tracking "{k}"'

def calc_environment_hash_dict():
    #Calculate a hash of the current environment, Should be very fast. Currently
    #this only gives something meaningful for conda environments, but it could
    #of course be extended to other environments (Python venvs, debian pkg list,
    #etc.).
    import os
    cp = os.environ.get('CONDA_PREFIX')
    if cp:
        ch =  _calc_conda_env_hash( cp )
        return dict( conda_env_pkg_hash
                     = ch or '@@conda_env_with_unknown_hash@@' )
    return {}

def _calc_conda_env_hash( conda_prefix ):
    """Get a checksum (hex str) of the files in $CONDA_PREFIX/conda-meta, which
    can be used to detect if installed packages in a given conda environment
    changed or not. Returns None if CONDA_PREFIX is not set. Raises a runtime
    error in case of problems with the current conda environment.

    To be fast, it is assumed that the filenames in $CONDA_PREFIX/conda-meta are
    enough to detect any changes.

    """
    assert conda_prefix
    import pathlib
    cp = pathlib.Path( conda_prefix ) / 'conda-meta'
    if not cp.is_dir():
        raise RuntimeError('Did not find a conda-meta directory'
                           ' inside $CONDA_PREFIX')
    import hashlib
    hashval = hashlib.md5()
    hashval.update(str(cp.absolute().resolve()).encode())
    for f in sorted(cp.iterdir(),key = lambda p : str(p) ):
        hashval.update(f.name.encode())
    return hashval.hexdigest()
