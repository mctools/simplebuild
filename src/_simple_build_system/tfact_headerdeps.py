from . import target_base
from . import includes
from . import utils
from . import dirs
from . import db
import os
from . import langs

class TargetIncDep(target_base.Target):
    #for header files not part of an inderdependent circular group or for such a circular group.
    def __init__(self,pkg,subdir,fn,pub,priv,possible_privincs,igroup=None):
        self.pkglevel = False#does not need a pkglevel dep, just needs to be present as possible dependency
        isgroup = (igroup is not None)
        assert bool(isgroup)==bool(isinstance(fn,set))
        self.name='%s__%s__%s'%(pkg.name,subdir,('group%i'%igroup if isgroup else fn))
        self.pkgname=pkg.name
        self.code = []

        # NOTE THAT FOLLOWING LINES OF CODE ARE SIMILAR TO ONES IN tfact_binary.py !!!

        #deal with the private dependencies as well as public deps to same pkg
        #here, postpone the other public ones until setup() when other packages are available.
        self.__pklfile=dirs.pkg_cache_dir(pkg,('%s__group%i'%(subdir,igroup) if isgroup else '%s__%s'%(subdir,fn)))
        self.deps=[dirs.makefile_blddir(self.__pklfile)]
        for f in (fn if isgroup else [fn]):
            self.deps += [dirs.makefile_pkg_dir(pkg,subdir,f)]#only actual file dependencies
        self._pkloffset=len(self.deps)
        if priv and possible_privincs:
            for p in priv:
                if p in possible_privincs:
                    self.deps+=['%s__%s__%s'%(pkg.name,subdir,p)]
        if pub:
            pkg.update_incs()
            incs=db.db['pkg2inc'][pkg.name]
            self.deps += ['%s__libinc__%s'%(p,f) for (p,f) in pub if (p==self.pkgname and f in incs)]
            self._pub = [(p,f) for (p,f) in pub if p!=self.pkgname]
        else:
            self._pub=None

    def setup(self,pkg):
        # NOTE THAT FOLLOWING LINES OF CODE ARE SIMILAR TO ONES IN tfact_binary.py !!!
        if self._pub:
            p2i=db.db['pkg2inc']
            d=pkg.deps_names()
            self.deps+=['%s__libinc__%s'%(p,f) for (p,f) in self._pub if (p in d and f in p2i.get(p,[]))]
        pklcont=set(self.deps[self._pkloffset:])
        utils.mkdir_p(os.path.dirname(self.__pklfile))
        utils.update_pkl_if_changed(pklcont,self.__pklfile)

class TargetIncDep_HeaderFileInGroup(target_base.Target):
    #For a single header file in a circular group
    def __init__(self,pkg,subdir,fn,igroup):
        self.pkglevel = False#does not need a pkglevel dep, just needs to be present as possible dependency
        self.name='%s__%s__%s'%(pkg.name,subdir,fn)
        self.pkgname=pkg.name
        self.code = []
        self.deps = ['%s__%s__group%i'%(pkg.name,subdir,igroup)]

def find_circ(hh,hh2local,l,circgroups):
    local = hh2local[hh]
    if not local:
        return#no unresolved local includes
    for hhl in local:
        if hhl in l:
            #New circular group! Some circular groups have multiple circular routes within
            #the group, so we must check for overlap with existing groups and merge:
            newcg=set(l[l.index(hhl):])
            overlaps=[]
            for cg in circgroups:
                if not cg.isdisjoint(newcg):
                    overlaps+=[cg]
                    newcg.update(cg)
            for ol in overlaps:
                circgroups.remove(ol)
            if len(newcg)>1:#don't treat files with self-includes as groups (let the compiler complain later)
                circgroups+=[newcg]
        else:
            #continue with next layer of includes:
            find_circ(hhl,hh2local,l+[hhl],circgroups)
    hh2local[hh]=None#prevent recheck

def tfactory_headerdeps(pkg,subdir):
    hhs = langs.headers_in_dir(dirs.pkg_dir(pkg,subdir))
    hh2deps=dict((hh,includes.find_includes(dirs.pkg_dir(pkg,subdir,hh),pkg)) for hh in hhs)
    if not hh2deps and subdir=='libinc':
        from . import error
        error.error("No header files found in %s/%s (remove this directory if not needed)"%(pkg.name,subdir))
    #It is possible to have valid circular dependencies between header files in
    #the same dir. To solve this we must first detect such groups of interdependant files and
    #make special circular targets in the makefile:
    if subdir!='libinc':
        hh2local=dict((hh,hh2deps[hh][0]) for hh in hhs)
    else:
        hh2local={}
        for hh in hhs:
            deps= hh2deps.get(hh,(None,set()))[1]
            hh2local[hh]=set(fn for (pkgname,fn) in deps if pkgname==pkg.name) if deps else set()
    for hh,local in hh2local.items():
        if local:
            local.intersection_update(hhs)
    circgroups=[]
    for hh in hhs:
        find_circ(hh,hh2local,[],circgroups)
    hh2group={}
    for ig,cg in enumerate(circgroups):
        for hh in cg:
            hh2group[hh]=ig

    igroup2pub = {}
    igroup2priv = {}
    tgts=[]
    for hh,deps in hh2deps.items():
        igroup = hh2group.get(hh,None)
        if igroup is None:
            possible_privincs = hhs.difference(set([hh]))
            priv,pub=deps
            if subdir=='libinc':
                if pub:
                    pub = [(p,f) for (p,f) in pub if f!=hh]
            else:
                if priv and hh in priv:
                    priv.remove(hh)
            tgts+=[TargetIncDep(pkg,subdir,hh,pub,priv,possible_privincs)]
        else:
            tgts+=[TargetIncDep_HeaderFileInGroup(pkg,subdir,hh,igroup)]
            if deps[0]:
                if igroup not in igroup2priv:
                    igroup2priv[igroup]=deps[0]
                else:
                    igroup2priv[igroup].update(deps[0])
            if deps[1]:
                if igroup not in igroup2pub:
                    igroup2pub[igroup]=deps[1]
                else:
                    igroup2pub[igroup].update(deps[1])
    for igroup,group in enumerate(circgroups):
        priv=igroup2priv.get(igroup,None)
        pub=igroup2pub.get(igroup,None)
        possible_privincs = hhs.difference(set(group))
        if pub and subdir=='libinc':
            pub = [(p,f) for (p,f) in pub if f not in group]
        tgts+=[TargetIncDep(pkg,subdir,group,pub,priv,possible_privincs,igroup)]
    return tgts
