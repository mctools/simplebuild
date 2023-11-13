
_cache_version = [None]
def determine_version():
    if _cache_version[0] is None:
        import importlib.metadata
        try:
            #NB: Hardwiring python package name:
            version = importlib.metadata.version('simple-build-system')
        except importlib.metadata.PackageNotFoundError:
            # package is not installed (not really supported)
            version = 'unversioned_local_source'
        _cache_version[0] = version
    return _cache_version[0]
