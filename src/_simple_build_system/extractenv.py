import pathlib
from . import utils
from . import envcfg

def parse_stdouterr(fh):
    #Errors causes ec!=0 so are noticed by the user. But we want to capture
    #warnings so we can point them out later, and in particular this one:
    #
    #CMake Warning:
    #  Manually-specified variables were not used by the project:
    #
    #    BLA
    #    LALA
    #
    #
    n_warnings=0
    unused_var_mode=False
    unused_vars=[]
    for l in fh:
        l=l.rstrip()
        if not l:
            continue
        if l.startswith('CMake Warning:'):
            n_warnings += 1
            continue
        if n_warnings and 'Manually-specified variables were not used by the project:' in l:
            unused_var_mode = True
            continue
        if unused_var_mode:
            if l.startswith('  '):
                l=l.strip()
                assert l
                if l not in unused_vars:
                   unused_vars.append( l )
                continue
            else:
                assert unused_vars
                unused_var_mode=False
    assert bool(unused_vars)==bool(n_warnings)
    return {'other_warnings':n_warnings-(1 if unused_vars else 0),'unused_vars':unused_vars}

def parse(filename):
    extdeps = {}
    sysvars = {'langs':{}}
    cmakevars = {}
    for l in open(filename):
        c=l[0]
        if c=='#':
            continue
        l=[e.strip() for e in l.split('@',2)]
        if l[0]=='EXT':
            l[2:]=l[2].split('@',1)#can actually have 4 fields in this case, not just 3
            ext=l[1]
            if ext not in extdeps:
                extdeps[ext]={}
            if l[2]=='PRESENT':
                extdeps[ext]['present']=bool(int(l[3]))
            elif l[2]=='LINK':
                extdeps[ext]['ldflags']=l[3]
            #elif l[2]=='COMPILE':
            #    extdeps[ext]['cflags']=l[3]
            elif l[2]=='VERSION':
                extdeps[ext]['version']=l[3]
            elif l[2]=='COMPILE_CXX':
                extdeps[ext]['cflags_cxx']=l[3]
            elif l[2]=='COMPILE_C':
                extdeps[ext]['cflags_c']=l[3]
            else:
                assert False,"unexpected field: %s"%l[2]
        elif l[0]=='VAR':
            cmakevars[l[1]]=l[2]
        else:
            assert False



    sysvars['general'] = {
        'cmake_version': cmakevars['CMAKE_VERSION'],
        'system': cmakevars['CMAKE_SYSTEM'],
        'pybind11_embed_cflags_list' : cmakevars['PYBIND11_EMBED_CFLAGS_LIST'],
        'pybind11_embed_linkflags_list' : cmakevars['PYBIND11_EMBED_LINKFLAGS_LIST'],
        'pybind11_module_cflags_list' : cmakevars['PYBIND11_MODULE_CFLAGS_LIST'],
        'pybind11_module_linkflags_list' : cmakevars['PYBIND11_MODULE_LINKFLAGS_LIST'],
        'pybind11_version' : cmakevars['PYBIND11_VERSION'],
    }

    compiler_supports_rpathlink_flag = cmakevars['CAN_USE_RPATHLINK_FLAG']=='1'
    for lang in ['CXX','C','Fortran']:
        lvars={}
        if lang!='Fortran' or ('Fortran' in extdeps and extdeps['Fortran']['present']):
            lvars['cased'] = lang
            lvars['compiler'] = cmakevars['CMAKE_%s_COMPILER'%lang]
            lvars['compiler_version_long'] = cmakevars['CMAKE_%s_COMPILER_VERSION_LONG'%lang]
            lvars['compiler_version_short'] = cmakevars['CMAKE_%s_COMPILER_VERSION_SHORT'%lang]
            lvars['dep_versions'] = cmakevars['SBLD_GLOBAL_VERSION_DEPS_%s'%lang]
            cflags = ' '.join([cmakevars['CMAKE_%s_FLAGS'%lang],cmakevars.get('SBLD_GLOBAL_COMPILE_FLAGS_%s'%lang,'')])
            if lang=='C':
                cflags = ' '.join([c for c in cflags.split() if not (c.startswith('-std=c++') or c.startswith('-std=gnu++'))])
            elif lang=='CXX':
                cflags = ' '.join([c for c in cflags.split() if not (c.startswith('-std=c') and not c.startswith('-std=c++'))])
            lvars['cflags'] = cflags
            lvars['ldflags_prepend'] = cmakevars.get('SBLD_GLOBAL_LINK_FLAGS_PREPENDED','')
            lvars['ldflags'] = ' '.join([cmakevars['CMAKE_%s_LINK_FLAGS'%lang],cmakevars.get('SBLD_GLOBAL_LINK_FLAGS','')])
            lvars['name_obj'] = '%s'+cmakevars['CMAKE_%s_OUTPUT_EXTENSION'%lang]
            lvars['name_lib'] = cmakevars['CMAKE_SHARED_LIBRARY_PREFIX']+'%s'+cmakevars['CMAKE_SHARED_LIBRARY_SUFFIX']
            lvars['name_exe'] = '%s'

            cf_shlib = '${CFLAGSLANG_SHLIB_%s}'%lang.lower()
            cf_exe   = '${CFLAGSLANG_EXE_%s}'%lang.lower()
            lf='${LDFLAGSLANG_%s}'%lang.lower()
            lfprepend='${LDFLAGSPREPENDLANG_%s}'%lang.lower()

            lvars['create_obj_for_shlib'] = cmakevars['RULE_%s_COMPOBJ'%lang].replace('[FLAGS]','%s %%s'%cf_shlib).replace('[INPUT]','%s').replace('[OUTPUT]','%s')
            lvars['create_obj_for_exe']   = cmakevars['RULE_%s_COMPOBJ'%lang].replace('[FLAGS]','%s %%s'%cf_exe).replace('[INPUT]','%s').replace('[OUTPUT]','%s')
            lvars['create_lib'] = cmakevars['RULE_%s_SHLIB'%lang].replace('[FLAGS]','%s %s %s %%s'%(lfprepend,cf_shlib,lf)).replace('[INPUT]','%s').replace('[OUTPUT]','%s')
            lvars['create_exe'] = cmakevars['RULE_%s_EXECUTABLE'%lang].replace('[FLAGS]','%s %s %s %%s'%(lfprepend,cf_exe,lf)).replace('[INPUT]','%s').replace('[OUTPUT]','%s')

            lvars['rpath_flag_lib'] = cmakevars['RPATH_FLAG_%s_SHLIB'%lang]
            lvars['rpath_flag_exe'] = cmakevars['RPATH_FLAG_%s_EXECUTABLE'%lang]
            if lvars['rpath_flag_lib']:
                lvars['rpath_flag_lib'] += '%s'
            if lvars['rpath_flag_exe']:
                lvars['rpath_flag_exe'] += '%s'
            lvars['can_use_rpathlink_flag'] = compiler_supports_rpathlink_flag
        sysvars['langs'][lang.lower()]=lvars

    #copy parts of compilation setup into special volatile section to
    #determine if makefiles need to be rebuild (flags will belong in the
    #main Makefile and so changes in those will not need new package
    #makefiles):
    non_volatile=set(['cflags','ldflags','ldflags_prepend','compiler_version_long','compiler_version_short','dep_versions'])
    sysvars['volatile'] = dict((lang,dict((k,v) for k,v in info.items() if k not in non_volatile)) for lang,info in sysvars['langs'].items())
    sysvars['volatile']['sysgeneral'] = dict( (k,v) for k,v in sorted(sysvars['general'].items()) )

    sysvars['runtime']={'extra_lib_path':[e for e in cmakevars['SBLD_EXTRA_LDLIBPATHS'].split(';') if e],
                        'extra_bin_path':[e for e in cmakevars['SBLD_EXTRA_PATHS'].split(';') if e],
                        'libs_to_symlink':[e for e in cmakevars['SBLD_LIBS_TO_SYMLINK'].split(';') if e]}

    autoreconf={}
    autoreconf['bin_list'] = cmakevars['autoreconf_bin_list']
    autoreconf['env_list'] = cmakevars['autoreconf_env_list']
    cfgvars={'system':sysvars,'extdeps':extdeps,'autoreconf':autoreconf}

    return cfgvars

def extractenv(tmpdir,cmakedir,*,cmakeargs,actually_needed_extdeps,quiet=True,verbose=False):
    assert not (quiet and verbose)
    ec = utils.system("rm -rf %s/cmake/"%tmpdir)
    if ec!=0:
        return
    ec = utils.system("mkdir -p %s/cmake/"%tmpdir)
    if ec!=0:
        return
    from . import io as _io
    print = _io.print
    print("Inspecting environment via CMake")
    if     _io.is_quiet():
        capture = ' >& cmake_output21_capture.txt; exit ${PIPESTATUS[0]}'
    else:
        capture = ' 2>&1|tee cmake_output21_capture.txt; exit ${PIPESTATUS[0]}'

    #pass on conda cmake args:
    general_cmake_args = envcfg.var.cmake_args or ''
    if general_cmake_args:
        general_cmake_args = ' '+general_cmake_args

    import time
    t0 = time.time()
    ec = utils.system("cd %s/cmake/ && cmake%s%s%s%s %s %s%s"%(tmpdir,
                                                               general_cmake_args,
                                                               ' -DSBLD_QUIET=1' if quiet else '',
                                                               ' -DSBLD_VERBOSE=1' if verbose else '',
                                                               ' -DSBLD_ACTUALLY_USED_EXTDEPS=%s'%(':'.join(actually_needed_extdeps)),
                                                               ' '.join('-D'+a for a in cmakeargs),
                                                               cmakedir,
                                                               capture))
    t1 = time.time()
    print("Environment inspection done (%.2g seconds)"%(t1-t0))
    if ec!=0:
        return
    with ( pathlib.Path(tmpdir) / 'cmake' / 'cmake_output21_capture.txt' ).open('rt') as fh:
        printedinfo = parse_stdouterr(fh)
    writteninfo = parse('%s/cmake/cmakecfg.txt'%tmpdir)
    writteninfo['cmake_printinfo'] = printedinfo
    return writteninfo
