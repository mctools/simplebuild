_exported_cmds = []

def export_pkg( pkg ):
    #Trying to follow https://clang.llvm.org/docs/JSONCompilationDatabase.html
    from . import dirs
    wd = str(dirs.makefiledir)
    for t in pkg.targets:
        if hasattr(t,'export_compilation_commands'):
            for cmd, fileid in t.export_compilation_commands():
                _exported_cmds.append( {
                    'directory' : wd,
                    'command' : cmd,
                    'file' : fileid
                } )

def finalise( destfile ):
    import json
    from .io import print
    print(f"Exporting {len(_exported_cmds)} compilation commands to file: {destfile.absolute()}")
    destfile.write_text( json.dumps( _exported_cmds, indent='  ' ) )
