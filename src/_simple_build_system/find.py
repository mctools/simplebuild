import os
import fnmatch
from .grep import pkgfiles#, pkgdir_for_search
pjoin=os.path.join

def find(pkg,pattern):
    n=0
    #rd=pkgdir_for_search(pkg)
    rd=pkg.reldirname#always match on package reldir, even for dynamic packages!!
    pattern='*%s*'%pattern.lower()
    for flocal in pkgfiles(pkg):
        f = pjoin(rd,flocal)
        if fnmatch.fnmatch(f.lower(),pattern):
            ff=os.path.relpath(pjoin(pkg.dirname,flocal))
            print('match:',ff)
            n+=1
    return n

#col.grep_match
