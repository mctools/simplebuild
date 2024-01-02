"""

(obsolete - use 'FindData3') Python module providing access to data files of the
various packages

"""

import os
import sys

#We use a little class/sys.modules trick to allow both: Core.FindData(..) and
#Core.FindData.findData(..)

class _themodule:
    _os = os#this workaround is needed for some weird python2-lxplus
            #bug (DGSW-466)
    def findData(self,pkg,filename=None):
        if filename is None and not pkg.startswith('/'):
            fs=pkg.split('/')
            if len(fs)==2:
                ret = self.findData(*fs)
                if self._os.path.exists(ret):
                    return ret
            ret = pkg
        else:
            ret = self._os.path.join( self._os.environ['SBLD_DATA_DIR'],
                                      pkg,
                                      filename )
        return ret if self._os.path.exists(ret) else ""
    def __call__(self,pkg,filename=None):
        return self.findData(pkg,filename)
sys.modules[__name__] = _themodule()
