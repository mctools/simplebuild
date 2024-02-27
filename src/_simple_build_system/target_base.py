
# We have per-package make-files and targets. We also have a global DB to
# communicate header files and libraries between packages. In the same file as the
# global DB is in, we also keep info about the "last change" timestamps of
# packages as well as a list of previously enabled packages.
#
# All target objects must support pickling/depickling after their __init__ calls.
#
# * When neither a package nor any package it depends on has changed files, nothing
#   package specific is done and the makefile is left as it was.
#
# * When a package has changed files, its targets are completely recreated (and
#   pickled for future use). Their setup() calls are then done.
#
# * When a package has no changed files but there are changes in a pkg it depends
#   on, its targets are depickled and only setup() calls and the Makefile are redone.
#
# Global targets are also added, for now this is just a target which makes sure
# that the symlinks in ${INST}/include are up to date (NB: different symlinks are
# used for the actual build!)
#
# Thus, a target should implement two methods:
# #   __init__: Sets up object instance and perform as much work as can be done without knowing details of other packages.
# #             Also puts info needed by other pkgs into global db (libinc files + presence of libsrc)
# #             (remember to prune the global db when package is reconfed)
# #     <---- pickling happens here ---->
# #   setup: Performs work which depends on files in other packages.
#
#
#Derived classes should only keep members which can be pickled and will be valid
#in a subsequent invocation (i.e. don't store pkg objects!).
#
#It is OK to keep other target instances, but only if they are from the same package.

from . import col

need_commands_json_export = False


class Target:
    contains_message=False#todo: we should probably have a custom message in all targets
    pkglevel = True#set to false if other targets in the pkg depends on this
    isglobal = False

    def setup(self,pkg):
        #pkg==None if global target
        pass

    def validate(self):
        assert self.name#unique name (file or just a label)
        assert isinstance(self.name,str)
        if self.isglobal:
            assert self.pkgname is None
        else:
            assert self.pkgname
            assert isinstance(self.pkgname,str)
        assert isinstance(self.deps,list)#names of other targets which we depend on
        assert isinstance(self.code,list)#The code to run

class TargetPkgDone(Target):
    def __init__(self,pkg,pkgtargets):
        self.name=pkg.name
        self.pkgname=pkg.name
        self.deps=[t.name for t in pkgtargets if t.pkglevel]
        self.contains_message = True
        self.code = ['@if [ ${VERBOSE} -ge 0 ]; then echo "%sPackage %s done%s"; fi'%(col.bldcol('pkg'),self.pkgname,col.bldend)]
