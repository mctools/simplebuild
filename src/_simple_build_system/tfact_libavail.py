from . import target_base
from . import dirs
from . import utils

class TargetLibAvail(target_base.Target):
    def __init__(self,pkg):
        has_libsrc = pkg.has_lib()
        pklfile=dirs.pkg_cache_dir(pkg,'libavail.pkl')
        pklcont=has_libsrc
        mpf=dirs.makefile_blddir(pklfile)
        utils.update_pkl_if_changed(pklcont,pklfile)
        self.name='%s_libavail'%pkg.name
        self.pkgname=pkg.name
        self.deps=[mpf]
        self.code = []
        if has_libsrc:
            self.deps+=['%s_libsrc'%pkg.name]

def tfactory_libavail(pkg,dirtypes):
    #a silly little target whose only purpose in life is to make sure that
    #clients are relinked when a library disappears.
    #
    #(alternatively we could create an ldflag file and depend on it in bin targets)
    return [TargetLibAvail(pkg)]
