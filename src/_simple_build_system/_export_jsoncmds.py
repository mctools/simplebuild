_exported_cmds = []

def _eval_makefile_vars( s, varmap ):
    if '${' not in s:
        return s
    any_hits = False
    for k,v in varmap:
        _k = '${%s}'%k
        if _k in s:
            any_hits = True
            s = s.replace(_k,v)
    return _eval_makefile_vars(s, varmap) if any_hits else s

def export_pkg( pkg, varmap ):
    import pathlib
    #Trying to follow https://clang.llvm.org/docs/JSONCompilationDatabase.html
    #and the format used by CMake's -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    from . import dirs
    wd = str(dirs.makefiledir)
    for t in pkg.targets:
        if hasattr(t,'export_compilation_commands'):
            for cmd, sourcefile in t.export_compilation_commands():
                sf = pathlib.Path(_eval_makefile_vars(sourcefile,varmap))
                if not sf.exists():
                    from . import error
                    error.error('Exported json contains non-existing source'
                                ' file: %s'%sourcefile)
                _exported_cmds.append( {
                    'directory' : wd,
                    'command' : _eval_makefile_vars(cmd,varmap),
                    'file' : str(sf.absolute().resolve())
                } )

def finalise( destfile ):
    import json
    from .io import print
    import pathlib
    import os #need to use os.path.relpath in this case!
    dest_pretty = os.path.relpath(destfile.absolute(),pathlib.Path('.'))
    print(f"Exporting {len(_exported_cmds)} compilation"
          f" commands to file: {dest_pretty}")
    destfile.write_text( json.dumps( _exported_cmds, indent='  ' ) )
