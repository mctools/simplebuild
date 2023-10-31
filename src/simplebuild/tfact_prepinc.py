from . import dirs
from . import target_base
import os.path
from . import utils
from . import col
from . import db
join=os.path.join

pypkgname = __name__.split('.')[0]
assert pypkgname != '__main__'

class TargetPrepInc(target_base.Target):

    def __init__(self,pkg,has_compiled_target,has_libinc):
        self.pkgname=pkg.name
        self.name='%s_prepinc'%pkg.name
        self._privincdir=dirs.pkg_cache_dir(pkg,'inc')
        self._has_libinc=has_libinc
        self._has_compiled_target=has_compiled_target
        self._cachedir=dirs.pkg_cache_dir(pkg,'prepinc')
        self._pklfile = join(self._cachedir,'prepinc.pkl')
        mpf=dirs.makefile_blddir(self._pklfile)
        self.deps=[mpf]
        self.code = ['python3 -m%s.instsl2 %s ${VERBOSE}'%(pypkgname,mpf)]
        utils.mkdir_p(self._cachedir)
        self._neededlinks=set()
        if self._has_libinc:
            #contains_message=True
            self.code.insert(0,'@if [ ${VERBOSE} -ge 0 ]; then echo "  %sInstalling %s headers%s"; fi'%(col.bldcol('headers'),pkg.name,col.bldend))
            db.db['pkg2parts'][pkg.name].add('libinc')
            li=dirs.pkg_dir(pkg,'libinc')
            self._neededlinks.add((dirs.installdir / dirs.incdirname,pkg.name,li))
            if self._has_compiled_target:
                self._neededlinks.add((self._privincdir,pkg.name,li))
        #we also use this target to keep the DB of available public headers up to date (needed for header deps)
        pkg.update_incs()

    def setup(self,pkg):
        if self._has_compiled_target:
            for p in pkg.deps():
                d=dirs.pkg_dir(p,'libinc')
                if os.path.isdir(d):
                    self._neededlinks.add((self._privincdir,p.name,d))
        #only update pickle file when contents changed (to avoid triggering makefile targets):
        utils.update_pkl_if_changed(self._neededlinks,self._pklfile)

_compiled_patterns = set(['pycp', 'app_', 'libs'])#todo: to conf
def tfactory_prepinc(pkg,dirtypes):
    has_compiled_target = not dirtypes.isdisjoint(_compiled_patterns)
    has_libinc = 'libi' in dirtypes#the right way, but for now we use the following:
    if has_compiled_target or has_libinc:
        return [TargetPrepInc(pkg,has_compiled_target,has_libinc)]
    else:
        return []
