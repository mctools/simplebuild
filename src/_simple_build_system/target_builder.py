from . import target_base
from . import col
import os
import re
from . import dirs
from . import utils
from . import error
from . import conf

_patterns=[]
#dirtypes=set()
dirtype_info = {}
def register_pattern(pattern,target_factory):
    global _patterns,dirtypes_info#,dirtypes
    _patterns+=[pattern]
    dt=pattern[0:4]
    dirtype_info[dt] = (re.compile('^'+pattern+'$').match,target_factory)
    assert len(dirtype_info)==len(_patterns),"patterns not uniquely defined by first 4 chars"

for p,f in conf.target_factories_for_patterns():
    register_pattern(p,f)
nonpattern_tfacts=conf.target_factories()

def apply_patterns(pkg):
    targets=[]
    dn=dirs.pkg_dir(pkg)
    dirtypes=set()
    for d in os.listdir(dn):
        dirtype=d[0:4]
        nfo = dirtype_info.get(dirtype,None)
        dd=os.path.join(dn,d)
        if nfo and nfo[0](d) and os.path.isdir(dd):
            thefactory = nfo[1]
            ll=thefactory(pkg,d)#call factory
            #subdirs matching a target-generating pattern can not have subdirs themselves. This seems like a good place to check for it:
            for sf in os.listdir(dd):
                if sf=='.ipynb_checkpoints':
                    continue#ignore these as a workaround (although we should guard against them being committed)
                sf=os.path.join(dd,sf)
                if os.path.isdir(sf):
                    if os.path.basename(sf).startswith('__pycache__'):
                        continue
                    error.error('Sub-directories are not allowed in %s/%s/'%(pkg.name,d))
            if ll:
                dirtypes.add(dirtype)
                targets += ll
    return targets,dirtypes

def create_pkg_targets(pkg):
    assert not hasattr(pkg,'targets')
    #create targets for package
    targets=[]

    #find subdirs matching patterns and apply their associated target factory:
    pt,dt=apply_patterns(pkg)
    targets += pt

    for tf in nonpattern_tfacts:
        targets+=tf(pkg,dt)

    #Packages always have special done target which depends on all the other targets:
    targets += [target_base.TargetPkgDone(pkg,targets)]

    pkg.targets = targets

    d=dirs.pkg_cache_dir(pkg)
    utils.mkdir_p(d)
    utils.pkl_dump(targets,os.path.join(d,'targets.pkl'))

def load_pickled_pkg_targets(pkg):
    """Load the targets of the package from the pickle file written by
    create_pkg_targets (or None if absent or broken)."""
    t = utils.pkl_load_or_none(dirs.pkg_cache_dir(pkg,'targets.pkl'))
    if not isinstance(t,list) or not t:
        return None
    return t

class TargetGlobalSysModules(target_base.Target):
    isglobal=True
    contains_message=True
    def __init__(self):
        self.name='_global__sysmods'
        self.pkgname = None
        self.deps = []
        self.code = [
            '@if [ ${VERBOSE} -ge 0 ]; then echo "%sInstalling global system modules%s"; fi'%(col.bldcol('global'),col.bldend),
            'mkdir -p ${INST}/python/simplebuild',
            'touch ${INST}/python/simplebuild/__init__.py'
        ]
        self.deps += [
            '${BLD}/cfg.py',
            '${BLD}/_cfg_data.pkl'
        ]
        self.code += [
            'cp -f ${BLD}/cfg.py ${INST}/python/simplebuild/cfg.py',
            'cp -f ${BLD}/_cfg_data.pkl ${INST}/python/simplebuild/_cfg_data.pkl'
        ]


class TargetGlobalSbldpy(target_base.Target):
    #Installs the header-only C++ library and the Python runtime of sbldpy
    #(used by pymod_* subdirs):
    isglobal=True
    contains_message=True
    def __init__(self):
        import pathlib
        import shlex
        srcdir = pathlib.Path(__file__).parent / 'data' / 'sbldpy'
        hdr = srcdir / 'include' / 'sbldpy' / 'sbldpy.hh'
        pymod = srcdir / 'python' / 'sbldpy.py'
        incdir = '${INST}/%s/sbldpy'%conf.sbldpy_include_subdir
        self.name = conf.sbldpy_global_target
        self.pkgname = None
        self.deps = [ str(hdr), str(pymod) ]
        self.code = [
            '@if [ ${VERBOSE} -ge 0 ]; then echo "%sInstalling sbldpy%s"; fi'%(col.bldcol('global'),col.bldend),
            'mkdir -p %s ${INST}/python'%incdir,
            'cp -f %s %s/sbldpy.hh'%(shlex.quote(str(hdr)),incdir),
            'cp -f %s ${INST}/python/sbldpy.py'%shlex.quote(str(pymod)),
        ]

def create_global_targets():
    return [
        TargetGlobalSysModules(),
        TargetGlobalSbldpy(),
    ]
