
def load_env_cache( *keys ):
    import simplebuild.cfg as cfg
    import pickle
    with cfg.dirs.envcache.open('rb') as fh:
        data = pickle.load(fh)
    for k in keys:
        data = data[k]
    return data

def find_libpython():
    import shlex
    candidates=[]
    linkflags = load_env_cache('system',
                               'general',
                               'pybind11_embed_linkflags_list')
    allflags = []
    for lf in shlex.split(linkflags):
        for e in lf.split(';'):
            if e.strip():
                allflags.append(e.strip())
    candidates = [e for e in allflags
                  if (e.endswith('.so')
                      or '.so.' in e
                      or e.endswith('.dylib'))]
    if len(candidates)>1:
        candidates = [e for e in candidates
                      if 'python' in e.lower()]
    if len(candidates)>1:
        candidates = [e for e in candidates
                      if 'libpython' in e.lower()]
    if len(candidates)>1:
        candidates = [e for e in candidates
                      if e.endswith('/Python')]
    if len(candidates)==1:
        import pathlib
        p = pathlib.Path(candidates[0])
        if p.is_file():
            return p
    raise RuntimeError('Could not extract libpython location'
                       f' from pybind11 linkflags: {linkflags}')

if __name__ == '__main__':
    try:
        print( find_libpython() )
    except RuntimeError as e:
        raise SystemExit(str(e))
