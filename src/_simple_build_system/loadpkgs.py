import os
from pathlib import Path
from . import dirs
from . import langs
from . import conf
from . import error
join=os.path.join

def parse_depfile(pkgdir):
    filename=os.path.join(pkgdir,conf.package_cfg_file)
    pkg_name = os.path.basename(pkgdir)
    def _err(m=''):
        error.error('Package "%s" has invalid %s file%s'%(pkg_name,conf.package_cfg_file,m))
    with open(filename,'rt') as fh:
        for iline1,ll in enumerate(fh):
            ll=ll.split('#')[0].strip()
            if ll.startswith('package(') and ll.endswith(')'):
                ll=ll[8:-1]
                extdeps=[]
                pkgdeps=[]
                extra_cflags=[]
                extra_ldflags=[]
                extra_incdeps=[]
                current=None
                for e in ll.split():
                    if e=='USEPKG':
                        current=pkgdeps
                    elif e=='USEEXT':
                        current=extdeps
                    elif e=='EXTRA_COMPILE_FLAGS':
                        current=extra_cflags
                    elif e=='EXTRA_LINK_FLAGS':
                        current=extra_ldflags
                    elif e=='EXTRA_INCDEPS':
                        current=extra_incdeps
                    else:
                        if current is None:
                            _err()
                        current += [e]
                return ( set(extdeps),
                         set(pkgdeps),
                         extra_cflags,
                         extra_ldflags,
                         extra_incdeps )
        _err(' : missing package() statement.')

def _check_case_insensitive_duplication(path_str):
    path = Path(path_str)
    if not path.exists():
        return
    parentContent = [d.lower() for d in os.listdir(path.parent)]
    occurance = parentContent.count(path.name.lower())
    if not occurance == 1:
        from . import error
        error.error('Directory (and file) names differing only in casing are'
                    ' not allowed, due to being a potential source of error'
                    ' for different file systems. \nProblem occured with %s'%(path_str))

def find_pkg_dirs( basedir_list ):
    pkgdirs={}
    from .pkgutils import _find_pkg_dirs_under_basedir as _findpkgs
    for basedir in basedir_list:
      _check_case_insensitive_duplication(basedir)
      tmp_dirs = _findpkgs( basedir,
                            cfgfilename = conf.package_cfg_file )
      if tmp_dirs:
        pkgdirs.update({d:basedir for d in tmp_dirs})
      elif not basedir==dirs.main_bundle_pkg_root:
        error.error("No packages found in %s!"%basedir)
    return pkgdirs

class Package:
    #Only construct this with the PackageLoader

    def __lt__(self,o):
        assert self.name != o.name
        return self.name < o.name

    def __init__(self,basedir,reldirname,enabled):
        self.dirname = os.path.join(basedir,reldirname)
        self.dirpath = basedir.joinpath(reldirname)
        self.__haslib=None
        self.reldirname = reldirname
        #self.reldirnamewithparent = os.path.relpath(dirname,basedir+'/..')
        self.name = os.path.basename(reldirname)
        assert isinstance(self.name,str)
        assert isinstance(self.dirname,str)#fixme
        assert isinstance(self.reldirname,str)#fixme
        self.enabled=enabled
        self.is_setup=False
        self._any_parent_changed=False
        self.__deps_names=None
        self.__incs_updated=False
        self.__runnables=set()#to guard against clashes from scripts and app_, etc.
        self.__files_in_pkg_changed = False

    def register_runnable(self,n):
        if n in self.__runnables:
            error.error('Package "%s" provides multiple sources for the command "%s"'%(self.name,n))
        self.__runnables.add(n)

    def update_incs(self):
        if not self.__incs_updated:
            self.__incs_updated = True
            d=dirs.pkg_dir(self,'libinc')
            from . import db
            db.db['pkg2inc'][self.name]= langs.headers_in_dir(d) if os.path.isdir(d) else set()

    def setup(self,name2object,autodeps,*,enable_and_recurse_to_deps=False):
        #Ensures cfg file is parsed and direct dep links are established.
        #Recursively setups (and enables) deps if requested.
        if self.is_setup:
            return
        self.is_setup=True
        pcf=join(self.dirname,conf.package_cfg_file)
        ed,pd,cf,lf,extra_incdeps=parse_depfile(self.dirname)
        if self.name not in autodeps:
            pd.update(autodeps)
        self.direct_deps_extnames = ed
        self.direct_deps_pkgnames = pd
        self.direct_clients=set()
        self.extraflags_comp = cf
        self.extraflags_link = lf
        self.extra_include_deps = []
        for eid in extra_incdeps:
            eid=[e.strip() for e in eid.split(':')]
            if len(eid)!=2 or not eid[0] or not eid[1]:
                error.error('Malformed EXTRA_INCDEPS statement in %s'%pcf)
            self.extra_include_deps += [eid]

        ll=[]
        for n in pd:
            o=name2object(n)
            if not o:
                if n in autodeps:
                    error.error('Unknown package "%s" specified as auto dependency'%n)
                else:
                    error.error('Unknown package "%s" specified in %s'%(n,pcf))
            ll+=[o]
        self.direct_deps=ll
        if enable_and_recurse_to_deps:
            self.enabled=True
            for p in ll:
                p.setup(name2object,autodeps,enable_and_recurse_to_deps=True)
        self.__deps=None
        self.__extdeps=None
        self.__deplock=False

    def deps(self):
        #all pkgs we depend on, directly or indirectly.
        if self.__deps is not None:
            return self.__deps
        if self.__deplock:
            if self in self.direct_deps:
                error.error('Package "%s" depends on itself'%self.name)
            else:
                error.error('Detected circular dependency involving package "%s"'%self.name)
        self.__deplock=True
        d=set(self.direct_deps)
        for p in self.direct_deps:
            d.update(p.deps())
        self.__deplock=False
        self.__deps=d
        return d

    def deps_names(self):
        #names all pkgs we depend on, directly or indirectly, including ourselves.
        if self.__deps_names is not None:
            return self.__deps_names
        self.__deps_names = set(p.name for p in self.deps())
        return self.__deps_names

    def extdeps(self):
        #all extdeps we depend on, directly or indirectly.
        if self.__extdeps is not None:
            return self.__extdeps
        self.__extdeps=set(self.direct_deps_extnames)
        for p in self.direct_deps:
            self.__extdeps.update(p.extdeps())
        return self.__extdeps

    def disable(self):
        #Disable direct clients (only if we have actually been setup, otherwise we don't have direct_clients
        self.enabled=False
        _dc = self.direct_clients if hasattr(self,'direct_clients') else []
        for dc in _dc:
            dc.disable()

    def set_files_in_pkg_changed(self):
        self.__files_in_pkg_changed = True
        self.__set_parent_changed_recursively()
        self.__set_files_in_pkg_changed_recursively()

    def files_in_pkg_changed(self):
        return self.__files_in_pkg_changed

    def any_parent_changed(self):
        return self._any_parent_changed

    def __set_parent_changed_recursively(self):
        self._any_parent_changed=True
        for dc in self.direct_clients:
            dc.__set_parent_changed_recursively()

    def __set_files_in_pkg_changed_recursively(self):
        self.__files_in_pkg_changed=True
        for dc in self.direct_clients:
            dc.__set_files_in_pkg_changed_recursively()

    def has_lib(self):
        if self.__haslib is None:
            self.__haslib = os.path.isdir(dirs.pkg_dir(self,'libsrc'))
        return self.__haslib

    def all_clients(self):
        ic=set()
        ic.update(self.direct_clients)
        for c in self.direct_clients:
            ic.update(c.all_clients())
        return ic

    def info_as_dict(self):
        """Returns info as dictionary, containing not custom classes and suitable for
           pickling. Should be called after setup and after targets have been built, in
            order to guarantee complete info"""
        d = { 'name':self.name,
              'dirname':self.dirname,
              'reldirname':self.reldirname,
              'enabled' : self.enabled }
        if not self.enabled:
            return d
        from . import db
        d.update({ 'deps_pkgs' : self.deps_names(),
                   'deps_pkgs_direct' : self.direct_deps_pkgnames,
                   'deps_ext' : self.extdeps(),
                   'deps_ext_direct' : self.direct_deps_extnames,
                   'extraflags_comp' : self.extraflags_comp,
                   'extraflags_link' : self.extraflags_link,
                   'extra_include_deps' : self.extra_include_deps,
                   'has_lib' : self.has_lib(),
                   'clients' : [p.name for p in sorted(self.all_clients())],
                   'clients_direct' : [p.name for p in sorted(self.direct_clients)],
                   'runnables':db.db['pkg2runnables'].get(self.name,set()),
                   'reflogs':db.db['pkg2reflogs'].get(self.name,set()),
        })
        return d

    def dumpinfo(self,autodeps):
        from . import col
        from . import env
        width=max(75,len(self.dirname)+30)
        from .io import print, print_prefix
        def _format(ll):
            if not ll:
                return col.darkgrey+'<none>'+col.end
            from . import formatlist
            return '\n'.join(
                formatlist.formatlist(
                    [(n,col.ok if b else col.bad) for n,b in sorted(ll)],
                    width-40,
                    indent_first='',
                    indent_others=print_prefix+' '*27)
            )
        extdeps_direct = [(e,env.env['extdeps'][e]['present']) for e in self.direct_deps_extnames]
        extdeps_indirect = [(e,env.env['extdeps'][e]['present']) for e in self.extdeps() if e not in self.direct_deps_extnames]
        def nameformat(n):
            return n+'*' if n in autodeps else n
        clients_direct=[(nameformat(p.name),p.enabled) for p in self.direct_clients]
        clients_indirect=[(nameformat(p.name),p.enabled) for p in self.all_clients().difference(self.direct_clients)]
        deps_direct = [(nameformat(p.name),p.enabled) for p in self.direct_deps]
        deps_indirect = [(nameformat(p.name),p.enabled) for p in self.deps() if p not in self.direct_deps]

        s='='*int((width-len('Package information')-2)//2)
        l1='%s Package information %s'%(s,s)
        print(l1)
        print('Package name            : %s'%(_format([(self.name,self.enabled)])))
        print('Enabled                 : %s'%(_format([('Yes' if self.enabled else 'No',self.enabled)])))
        print('Relative location       : %s%s%s'%(col.blue,self.reldirname,col.end))
        print('Physical location       : %s%s%s'%(col.yellow,self.dirname,col.end))
        print('Direct relations')
        print('  Dependencies          : %s'%(_format(deps_direct)))
        print('  Clients               : %s'%(_format(clients_direct)))
        print('  External dependencies : %s'%(_format(extdeps_direct)))
        print('Indirect relations')
        print('  Dependencies          : %s'%(_format(deps_indirect)))
        print('  Clients               : %s'%(_format(clients_indirect)))
        print('  External dependencies : %s'%(_format(extdeps_indirect)))
        print('='*len(l1))

class PackageLoader:

    def __init__(self,
                 pkgdirs,
                 pkg_filter_obj=None,
                 autodeps=None,
                 load_all=False):
        """Locates package directories and inits wrapper Package objects for
        each.  It will respect select_pkg_filter and attempt to be economical
        about loading the package configuration files. Filters will receive
        package reldirname and basename as input.'
        """
        #use load_all to (inefficiently) load all cfg info even when filter is
        #set (for queries about pkg metadata)

        #pkg_filter_obj.dump()
        if pkg_filter_obj.fully_open():
            pkg_filter_obj = None

        #Note, when select_pkg_filter is set, we do not need to load ALL cfg
        #files, hence the difference in treatment below.
        self.autodeps=set(autodeps if autodeps else [])

        #1) Sanity check arguments:
        #Commented for now, since we want to enable both NOT= and ONLY=
        #variables at the same time. Leaving here in case we encounter
        #unexpected side-effects:
        #if select_pkg_filter and exclude_pkg_filter:
        #    error.error("Can't exclude packages when simultaneously "
        #                "requesting to enable only certain packages")

        #2) Construct Package objects and name->object maps:
        default_enabled = pkg_filter_obj is None

        n2p={}
        lowercased_pkgs=set()
        pkgs=[]
        from .pkgutils import pkgname_valid_or_errmsg
        for pd,basedir in pkgdirs.items():
            pkg_reldir = os.path.relpath(pd,basedir)
            pkg_name = os.path.basename(pd)
            assert len(pkg_name)>=3
            p=Package(basedir,pkg_reldir,default_enabled)
            pkgs+=[p]
            ln=p.name.lower()
            if p.name in n2p:
                error.error('Duplicate package name: "%s"'%p.name)
            if ln in lowercased_pkgs:
                clashes='" "'.join(p.name for p in pkgs if p.name.lower()==ln)
                error.error('Package names clash when'
                            ' lowercased: "%s" '%clashes)
            lowercased_pkgs.add(ln)
            pkgnameerrmsg = pkgname_valid_or_errmsg(p.name)
            if pkgnameerrmsg is not None:
                error.error(pkgnameerrmsg)
            n2p[p.name]=p
        self.pkgs=pkgs
        self.name2pkg=n2p

        #3) Load contents of all or some of the package config files.
        g=self.name2pkg.get
        def pkg_name2obj(pn):
            return g(pn,None)
        if pkg_filter_obj:
            for p in pkgs:
                if pkg_filter_obj.passes( p.name, p.reldirname ):
                    p.setup(pkg_name2obj,
                            autodeps,enable_and_recurse_to_deps=True)
        if load_all or not pkg_filter_obj:
            for p in pkgs:
                p.setup(pkg_name2obj,autodeps)

        #4) setup client links (only to clients which are setup):
        for p in pkgs:
            if p.is_setup:
                for pd in p.direct_deps:
                    if pd.is_setup:
                        pd.direct_clients.add(p)

        for p in self.enabled_pkgs_iter():
            p.deps()#must setup deps of all enabled packages, otherwise we can't be sure to detect circular deps

    def check_no_forbidden_extdeps( self, possible_extdeps ):
        for p in self.pkgs:
            if not hasattr(p,'direct_deps_extnames'):
                continue#pkg.info was never parsed (possibly the package was disabled by filter => do not load just to validate)
            forbidden = p.direct_deps_extnames - possible_extdeps
            forbidden = forbidden.pop() if forbidden else None
            if forbidden:
                error.error('Unknown external dependency "%s" specified in %s/%s'%(forbidden,p.dirname,conf.package_cfg_file)+
                          '\nAvailable values in this configuration are: "%s"'%'", "'.join(possible_extdeps))

    def enabled_pkgs_iter(self):
        for p in self.pkgs:
            if p.enabled:
                yield p

    def active_deps_extnames(self):
        s=set()
        for e in (p.direct_deps_extnames for p in self.enabled_pkgs_iter()):
            s.update(e)
        return s

    def disable_pkgs_with_extdeps(self,extdeps):
        if not extdeps:
            return#nothing to do
        prev_enabled=set(self.enabled_pkgs_iter())
        for p in self.pkgs:
            if p.enabled and not extdeps.isdisjoint(p.direct_deps_extnames):
                p.disable()
        return prev_enabled.difference(set(self.enabled_pkgs_iter()))
