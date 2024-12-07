import os
import pathlib
from . import conf
from . import target_base
from . import env
from . import dirs
from . import langs
from . import utils
from . import includes
from . import col
from . import db
from . import error
from . import envcfg
from . import tfact_headerdeps

join=os.path.join

def _sort_extdep_list( extdeps ):
    if not extdeps or len(extdeps) <= 1:
        return
    _ed = env.env['extdeps']
    def extdep_sort_key( extdepname ):
        i = _ed[extdepname]
        return ( i['flagpriority'], extdepname )
    extdeps.sort( key = extdep_sort_key )


class TargetBinaryObject(target_base.Target):
    def __init__(self,pkg,subdir,bn,e,lang,shlib,cflags,possible_privincs):
        is_py_mod = subdir.startswith('pycpp_')#todo better way?
        langinfo=env.env['system']['langs'][lang]
        self.pkglevel=False#needed by the corresponding TargetBinary object
        self.pkgname=pkg.name
        self._fn=bn+e
        self._lang=lang
        self._shlib=shlib
        d=dirs.makefile_pkg_cache_dir(pkg,'objs',subdir)
        self.name=join(d,langinfo['name_obj']%bn)
        fn=bn+e
        sf=dirs.makefile_pkg_dir(pkg,subdir,fn)
        self.__pklfile=dirs.pkg_cache_dir(pkg,'objs',subdir,fn+'_deps.pkl')
        self.deps=[dirs.makefile_blddir(self.__pklfile)]
        self.deps+=['${LANG}/%s'%lang,'%s_prepinc'%pkg.name,sf]#FIXME perhaps on /cxxpch in case of cxx? (if has pch reqs)
        extra_flags=['-I%s'%dirs.makefile_pkg_cache_dir(pkg,'inc'),'-DPACKAGE_NAME=%s'%pkg.name]

        if cflags:
            extra_flags+=cflags
        if shlib:
            extra_flags+=['-fPIC']#Could we get this from cmake already??

        #Get extdeps in order of priority (so we can use FLAGPRIORITY to force
        #some extdeps to set their include paths earlier than others).
        extdeps_sorted = list(pkg.extdeps())
        _sort_extdep_list(extdeps_sorted)

        for extdep in extdeps_sorted:
            extra_flags+=['${CFLAGS_%s_%s}'%(('CXX' if lang=='cxx' else 'C'),extdep)]
            self.deps+=['${EXT}/%s'%extdep]

        if lang=='cxx':
            #NB: Only allow pybind for C++ and never for libsrc/*.cc:
            if is_py_mod:
                #src in pycpp_*/*.cc
                assert shlib
                extra_flags.append( '${PYBIND11_MODULE_CFLAGS}' )
            elif not shlib:
                #C++ src in app_*/*.cc
                extra_flags.append( '${PYBIND11_EMBED_CFLAGS}' )

        if pkg.extraflags_comp:
            extra_flags+=pkg.extraflags_comp

        #contains_message=True
        obj_create_key = 'create_obj_for_shlib' if shlib else 'create_obj_for_exe'

        obj_create_cmd = langinfo[obj_create_key]%( ' '.join(extra_flags),
                                                    sf,
                                                    self.name )
        filekey = '%s/%s/%s'%(pkg.name,
                              subdir,
                              os.path.basename(self.name))

        if target_base.need_commands_json_export:
            self.__jsonexport = [ ( obj_create_cmd, sf) ]


        self.code=['@if [ ${VERBOSE} -ge 0 ]; then echo " '
                   ' %sBuilding %s%s"; fi'%(col.bldcol('objectfile'),
                                            filekey,
                                            col.bldend),
                   'mkdir -p %s'%d,
                   obj_create_cmd]

        priv,pub = includes.find_includes(dirs.pkg_dir(pkg,subdir,fn),pkg)

        # NOTE THAT FOLLOWING LINES OF CODE ARE SIMILAR TO ONES IN tfact_headerdeps.py !!!

        #deal with the private dependencies as well as public deps to same pkg
        #here, postpone the other public ones until setup() when other packages are available.
        self._pkloffset=len(self.deps)
        if priv and possible_privincs:
            for p in priv:
                if p in possible_privincs:
                    self.deps+=['${TRG}/%s__%s__%s'%(pkg.name,subdir,p)]
        if pub:
            pkg.update_incs()
            incs=db.db['pkg2inc'][pkg.name]
            self.deps += ['${TRG}/%s__libinc__%s'%(p,f) for (p,f) in pub if (p==self.pkgname and f in incs)]
            self._pub = [(p,f) for (p,f) in pub if p!=self.pkgname]
        else:
            self._pub=None

    def export_compilation_commands(self):
        return self.__jsonexport

    def setup(self,pkg):
        if self._pub:
            # NOTE THAT FOLLOWING LINES OF CODE ARE SIMILAR TO ONES IN tfact_headerdeps.py !!!
            p2i=db.db['pkg2inc']
            d=pkg.deps_names()
            self.deps+=['${TRG}/%s__libinc__%s'%(p,f) for (p,f) in self._pub if (p in d and f in p2i.get(p,[]))]
        pklcont=set(self.deps[self._pkloffset:])
        utils.mkdir_p(os.path.dirname(self.__pklfile))
        utils.update_pkl_if_changed(pklcont,self.__pklfile)

class TargetBinary(target_base.Target):

    def __init__(self,pkg,subdir,lang,shlib,object_targets,instsubdir,namefct,descrfct=None,checkfct=None):
        is_py_mod = subdir.startswith('pycpp_')#todo better way?
        db.db['pkg2parts'][pkg.name].add(subdir)
        langinfo=env.env['system']['langs'][lang]
        self.pkgname=pkg.name
        self._subdir=subdir

        pattern='name_lib' if shlib else 'name_exe'
        filename=namefct(pkg,subdir,langinfo[pattern])
        if checkfct:
            checkerrmsg = checkfct(pkg,subdir,filename)
            if checkerrmsg:
                error.error(checkerrmsg)

        if subdir.startswith('app_'):
            assert not shlib
            pkg.register_runnable(filename)
            db.db['pkg2runnables'].setdefault(pkg.name,set()).add(filename)

        dcol,descr = descrfct(pkg,subdir,filename) if descrfct else ('','%s/%s'%(pkg.name,filename))
        dcolend = col.bldend if dcol else ''
        self.name='%s_%s'%(pkg.name,subdir)

        self.deps=[]
        for ot in object_targets:
            self.deps.append(ot.name)
        self.deps.sort()
        sobjs=' '.join(self.deps)
        cachedir=dirs.pkg_cache_dir(pkg,'objs')
        utils.mkdir_p(cachedir)
        objlistfile=join(cachedir,'objs_%s.txt'%subdir)#to make sure we rebuild when removing a src file
        self.deps+=[dirs.makefile_blddir(objlistfile)]#'%s_prepinc'%pkg.name]
        extra_flags=[]
        extra_flags+=['%s']#This is used in self.setup() to add in library deps.

        extdeps_sorted = list(pkg.extdeps())
        _sort_extdep_list(extdeps_sorted)
        for extdep in extdeps_sorted:
            extra_flags+=['${LDFLAGS_%s} ${LDFLAGS_%s_%s_%s}'%(extdep,extdep,('LIB' if shlib else 'EXE'),lang)]
        if pkg.extraflags_link:
            extra_flags+=pkg.extraflags_link
        rpath_pattern = langinfo['rpath_flag_lib' if shlib else 'rpath_flag_exe']
        def append_to_rpath( extra_flags, p ):
            extra_flags += [ rpath_pattern%str(p) ]
            if langinfo['can_use_rpathlink_flag'] and '-rpath' in rpath_pattern and '-rpath-link' not in rpath_pattern:
                extra_flags += [ rpath_pattern.replace('-rpath','-rpath-link')%str(p) ]
        append_to_rpath( extra_flags, join('${INST}','lib') )
        append_to_rpath( extra_flags, join('${INST}','lib','links') )

        if lang=='cxx':
            #NB: Only allow pybind for C++ and never for libsrc/*.cc:
            if is_py_mod:
                #src in pycpp_*/*.cc
                assert shlib
                extra_flags.append( '${PYBIND11_MODULE_LDFLAGS}' )
            elif not shlib:
                #C++ src in app_*/*.cc
                extra_flags.append( '${PYBIND11_EMBED_LDFLAGS}' )

        conda_prefix =  envcfg.var.conda_prefix
        if conda_prefix:
            _cp = pathlib.Path(conda_prefix) / 'lib'
            if _cp.is_dir():
                append_to_rpath( extra_flags, _cp)
        if not os.path.exists(objlistfile) or open(objlistfile).read()!=sobjs:
            open(objlistfile,'w').write(sobjs)
        d=join('${INST}',instsubdir)
        #contains_message=True
        pattern = 'create_lib' if shlib else 'create_exe'
        if shlib and '-fPIE' in extra_flags:
            #-fPIE is for position independent executables, not libraries:
            extra_flags = [e for e in extra_flags if e!='-fPIE']
        self.code=['@if [ ${VERBOSE} -ge 0 ]; then echo "  %sCreating %s%s"; fi'%(dcol,descr,dcolend),
                   'mkdir -p %s'%d,
                   langinfo[pattern]%(' '.join(extra_flags),
                                      sobjs,
                                      join(d,filename))]

    def setup(self,pkg):
        ll=[]
        if self._subdir!='libsrc':
            if pkg.has_lib():
                ll += [conf.libldflag(pkg)]
            self.deps += ['%s_libavail'%self.pkgname]
        for p in pkg.deps():
            if p.has_lib():
                ll += [conf.libldflag(p)]
            self.deps+=['%s_libavail'%p.name]
        if ll:
            ll.insert(0, '-L${INST}/lib')
        self.code[-1]=self.code[-1]%(' '.join(ll))

def create_tfactory_binary(instsubdir=None,pkglib=False,shlib=False,allowed_langs=None,namefct=None,flagfct=None,descrfct=None,checkfct=None):
    if not allowed_langs:
        allowed_langs = langs.langs
    if pkglib:
        shlib=True
        instsubdir='lib'
    blainstsubdir=instsubdir#weird that we need this to propagate the variables into the next function

    def tfact_bin(pkg,subdir):
        instsubdir=blainstsubdir
        if '%s' in instsubdir:
            instsubdir = instsubdir%pkg.name
        srcs=[]
        hdrs=[]
        langspresent=set()
        skip_fct = None

        for f in utils.listfiles(dirs.pkg_dir(pkg,subdir),ignore_logs=subdir.startswith('app_')):
            n,e=os.path.splitext(f)
            assert n
            langsrc = langs.srcext2lang.get(e,None)
            if langsrc:
                langspresent.add(langsrc)
                if skip_fct and skip_fct(n):
                    continue
                srcs+=[(n,e,langsrc)]
                continue
            langhdr = None if langsrc else langs.hdrext2lang.get(e,None)
            if langhdr:
                langspresent.add(langhdr)
                hdrs+=[(n,e,langhdr)]
                continue
            error.error("File is neither src or header file of allowed language: %s"%f)

        if not srcs:
            error.error("No source files found in %s/%s (remove this directory if not needed)"%(pkg.name,subdir))
        if len(langspresent)!=1:
            assert len(langspresent)>1
            error.error("Files for multiple languages found in %s/%s"%(pkg.name,subdir))
        langspresent=langspresent.pop()
        if langspresent not in allowed_langs:
            error.error("Files of language '%s' found in %s/%s where only allowed languages are '%s'"%(langspresent,
                                                                                                       pkg.name,subdir,
                                                                                                       ';'.join(allowed_langs)))
        tgts=[]
        extra_cflags=flagfct(pkg,subdir) if flagfct else []

        possible_privincs = langs.headers_in_dir(dirs.pkg_dir(pkg,subdir))
        for bn,e,lang in srcs:
            tgts+=[TargetBinaryObject(pkg,subdir,bn,e,lang,
                                      shlib=shlib,cflags=extra_cflags,
                                      possible_privincs=possible_privincs)]
        tb=TargetBinary(pkg,subdir,langspresent,
                        shlib=shlib,object_targets=tgts,
                        instsubdir=instsubdir,namefct=namefct,descrfct=descrfct,
                        checkfct=checkfct)
        if pkglib:
            pkg.libtarget=tb
        tgts+=[tb]

        tgts += tfact_headerdeps.tfactory_headerdeps(pkg,subdir)

        return tgts
    return tfact_bin


