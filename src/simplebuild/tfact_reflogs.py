import os
from . import target_base
from . import utils
from . import dirs
from . import conf
from . import col
from . import error
from . import db
join = os.path.join
basename=os.path.basename

pypkgname = __name__.split('.')[0]
assert pypkgname != '__main__'

class TargetRefLogs(target_base.Target):
    def __init__(self,pkg,applogs,scriptlogs):
        #No need for this, since each package will always have this part:
        #db.db['pkg2parts'][pkg.name].add('testref_links')
        targetdir=dirs.installdir / 'tests/testref'
        utils.mkdir_p(targetdir)
        neededlinks=set()
        for f in applogs:
            tn = '%s.log'%conf.runnable_name(pkg,basename(os.path.dirname(f))[4:])
            neededlinks.add((targetdir,tn,f))
        for f in scriptlogs:
            tn = '%s.log'%conf.runnable_name(pkg,basename(f)[:-4])
            neededlinks.add((targetdir,tn,f))
        d=dirs.pkg_cache_dir(pkg,'testref')
        utils.mkdir_p(d)
        pklfile=join(d,'testref.pkl')
        mpf=dirs.makefile_blddir(pklfile)
        utils.update_pkl_if_changed(neededlinks,pklfile)
        for _,tn,_ in neededlinks:
            db.db['pkg2reflogs'].setdefault(pkg.name,set()).add(tn)

        self.name='%s_reflogs'%pkg.name
        self.pkgname=pkg.name
        self.deps=[mpf]
        self.code = ['@if [ ${VERBOSE} -ge 0 ]; then echo "  %sUpdating symlinks %s/testlogs%s"; fi'%(col.bldcol('symlink'),pkg.name,col.bldend),
                     'python3 -m%s.instsl2 %s ${VERBOSE}'%(pypkgname,mpf)]

def tfactory_reflogs(pkg,dirtypes):
    #Must complain about any .log file in app_* which is not test.log
    #Must complain about any .log file in scripts/ which does not have an associated script

    applogs,scriptlogs=[],[]
    if 'app_' in dirtypes:
        applogs = [f for f in dirs.pkg_dir(pkg).glob('app_*/*.log') if not conf.ignore_file(f)]
        for f in applogs:
            if basename(f)!='test.log' or utils.is_executable(f):
                if basename(f)!='test.log':
                    e='Log files in app_* dirs can only be named "test.log".'
                if utils.is_executable(f):
                    e='Log files should not be executable (correct by running chmod -x <filename>).'
                error.error('%s\n\nProblematic file: %s'%(e,f))
    if 'scri' in dirtypes:
        scriptlogs = [f for f in dirs.pkg_dir(pkg,'scripts').glob('*.log') if not conf.ignore_file(f)]
        for f in scriptlogs:
            sf,ext = os.path.splitext(f)
            assert ext=='.log'
            if not os.path.exists(sf):
                error.error('Log file in script dir does not have a corresponding script!\n',
                            'Problematic file: %s'%f,
                            'Missing script: %s'%sf)
            if utils.is_executable(f):
                error.error('Log files should not be executable (correct by running chmod -x <filename>)!\n',
                            'Problematic file: %s'%f)
    #always create since we want to also undo links:
    #if not applogs and not scriptlogs:
    #    return []
    return [TargetRefLogs(pkg,applogs,scriptlogs)]
