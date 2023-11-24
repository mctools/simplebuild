_cache = [None]
def locate_master_cfg_file():
    if _cache[0] is None:
        _cache[0] = _actual_locate_master_cfg_file()
    return _cache[0]

def _actual_locate_master_cfg_file():
    #Be very conservative about imports here!
    import os
    import pathlib
    def err(msg):
        from . import error
        error.error(msg)
    p = os.environ.get('SIMPLEBUILD_CFG')
    if p:
        p = pathlib.Path(p).expanduser()
        if not p.exists():
            err('SIMPLEBUILD_CFG was set to a non-existing directory or file')
        if p.is_dir():
            p = p / 'simplebuild.cfg'
            if not p.exists():
                err('SIMPLEBUILD_CFG was set to a directory'
                            ' with no simplebuild.cfg file in it')
        else:
            if not p.exists():
                err('SIMPLEBUILD_CFG was set to non-existing file')
        if not p.is_absolute():
            err('SIMPLEBUILD_CFG must be set to an absolute path')
        return p
    p = pathlib.Path('.').absolute()#NB: NOT .resolve() on purpose!
    f = p / 'simplebuild.cfg'
    if f.exists():
        return f
    for p in sorted(p.parents,reverse=True):
        f = p / 'simplebuild.cfg'
        if f.exists():
            return f
