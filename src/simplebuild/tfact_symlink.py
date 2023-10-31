import os
from . import db
from . import col
from . import error
from . import dirs
from . import utils
from . import target_base
join=os.path.join

pypkgname = __name__.split('.')[0]
assert pypkgname != '__main__'

class TargetSymlinks(target_base.Target):
    def __init__(self,pkg,linktype,srcdir,destdir,files,chmodx,renamefct=None,runnables=False):
        db.db['pkg2parts'][pkg.name].add('symlink__%s'%linktype)
        self.name='%s_symlink_%s'%(pkg.name,linktype)
        self.linktype=linktype
        self._cachedir = dirs.pkg_cache_dir(pkg,'symlinks')
        self.files=files
        self.srcdir=srcdir
        self.destdir=destdir
        self.renamefct=renamefct
        self.pkgname=pkg.name
        self.chmodx=chmodx
        pklfile = join(self._cachedir,'%s.pkl'%self.linktype)
        mpf=dirs.makefile_blddir(pklfile)
        self.deps=[mpf]
        self.code = ['@if [ ${VERBOSE} -ge 0 ]; then echo "  %sUpdating symlinks %s/%s%s"; fi'%(col.bldcol('symlink'),
                                                                                                pkg.name,linktype,col.bldend),
                     'python3 -m%s.instsl %s ${VERBOSE}'%(pypkgname,mpf)]

        pklcont=[]
        for f in self.files:
            absf=join(self.srcdir,f)
            assert not os.path.isdir(absf)#should not happen since listfiles ignores subdirs
            if self.chmodx is not None and self.chmodx != utils.is_executable(absf):
                error.error('File must %sbe executable: %s'%('' if self.chmodx else 'not ',os.path.realpath(absf)),
                            '\nYou can correct it by running the command:\n',
                            '    chmod %sx %s'%('+' if self.chmodx else '-',os.path.realpath(absf)))
            dirs.makefile_instdir(self.destdir)
            if self.renamefct:
                r=self.renamefct(pkg,f)
                #dest=dirs.makefile_instdir(self.destdir,r)
            else:
                r=f
                #dest=dirs.makefile_instdir(self.destdir)
            if runnables:
                pkg.register_runnable(r)
                db.db['pkg2runnables'].setdefault(pkg.name,set()).add(r)

            pklcont+=[(f,r)]

        utils.mkdir_p(self._cachedir)
        pklcont = (pklcont,self.srcdir,self.destdir)
        #only update pickle file when contents changed (to avoid triggering makefile targets):
        utils.update_pkl_if_changed(pklcont,pklfile)

def create_tfactory_symlink(filepattern,destdir,chmodx,renamefct=None):
    import re
    match=re.compile(filepattern).match
    destdirabs=str(dirs.installdir / destdir) #converting to string to enable value insertion
    destdir_needs_pkgname = '%s' in destdir
    lf=utils.listfiles
    def tfactory_symlink(pkg,subdir):
        dd=destdirabs%pkg.name if destdir_needs_pkgname else destdirabs
        srcdir=dirs.pkg_dir(pkg,subdir)
        ignore_logs=False
        if subdir=='scripts' or subdir.startswith('app_'):
            ignore_logs=True#handled in the reflogs target
        files=[f for f in lf(srcdir,match,ignore_logs=ignore_logs)]
        if not files:
            error.error("No suitable files found in %s/%s (remove this directory if not needed)"%(pkg.name,subdir))

        return [TargetSymlinks(pkg,subdir,srcdir,dd,files,chmodx=chmodx,renamefct=renamefct,runnables=(subdir=='scripts'))]
    return tfactory_symlink
