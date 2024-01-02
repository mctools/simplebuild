"Python module providing access to data files of the various packages"

#This is the python3 version, always returning pathlib paths.

import os
import sys
import pathlib

#We use a little class/sys.modules trick to allow both: Core.FindData(..) and
#Core.FindData.findData(..)

class _themodule:
    def _resolvepp(self,pp):
        return pp.resolve() if pp.exists() else None
    def _resolvepnfn(self,pn,fn):
        _ = pathlib.Path(os.path.join(os.environ['SBLD_DATA_DIR'],pn,fn))
        return self._resolvepp(_)
    def findData(self,pkg,filename=None):
        if filename is not None:
            return self._resolvepnfn(pkg,filename)
        if isinstance(pkg,pathlib.PurePath):
            return self._resolvepp(pkg)#already pathlib path
        #We were given a single argument which is not a pathlib path. Assume it
        #is a string, either in the form of a path, or in the form
        #"<pkgname>/<filename>":
        if not pkg.startswith('/'):
            fs=pkg.split('/')
            if len(fs)==2:
                _=self._resolvepnfn(*fs)
                if _:
                    return _
        return self._resolvepp(pathlib.Path(pkg))
    def __call__(self,pkg,filename=None):
        return self.findData(pkg,filename)
sys.modules[__name__] = _themodule()
