
def setup(app):
    """Install the plugin."""
    from ._determine_version import determine_version
    version = determine_version()

    app.add_role('sbpkg', sbpkg_role)
    app.add_config_value('simplebuild_pkgbundles', None, 'env')
    return { 'version' : version }

#FIXME: optional url-exists checking? For the CI mainly I guess.

def sbpkg_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    """Link to the source code of a given simplebuild package."""
    from .pkgutils import pkgname_valid_or_errmsg
    app = inliner.document.settings.env.app
    def _err(msg = None):
        _msg = inliner.reporter.error( msg or 'Syntax error in: "%s"'%text,
                                       line = lineno)
        return ( [inliner.problematic(rawtext, rawtext, _msg)],
                 [_msg] )

    linkinput = text.strip()
    override_text = None
    if '<' in linkinput:
        _parts = [e.strip() for e in linkinput.split('<')]
        if not len(_parts)==2 or not _parts[1].endswith('>'):
            return _err()
        _parts[1] = _parts[1][:-1].strip()
        _parts = [e.strip() for e in _parts if e.strip()]
        if len(_parts)!=2 or not all( (e and '>' not in e) for e in _parts ):
            return _err()
        override_text, linkinput = _parts

    _parts = [p.strip() for p in linkinput.split('/',1) if p.strip()]
    if len(_parts) not in (1,2):
        return _err()
    pkgname,subpath = (_parts[0],None) if len(_parts) == 1 else _parts
    _ = pkgname_valid_or_errmsg( pkgname )
    if _ is not None:
        return _err(_)
    sbpkgs = load_sbpkgs(app)
    if sbpkgs['error_msg'] is not None:
        return _err(sbpkgs['error_msg'])
    pkginfo = sbpkgs['pkgs'].get(pkgname)
    if not pkginfo:
        return _err('Could not find package named "%s"'%pkgname)
    url = pkginfo['pkgdir_url']
    linktext = pkgname
    if subpath:
        _=pkginfo['pkgdir_local'] / subpath
        if not _.is_file():
            return _err(f'File not found in package: {_}')
        url += '/%s'%subpath
        linktext += '/%s'%subpath
    if override_text:
        linktext = override_text
    node = _create_link_node(rawtext, app, linktext, url, options)
    return [node], []

def _create_link_node(rawtext, app, linktext, linkurl, options):
    from docutils import nodes as _du_nodes
    from docutils.parsers.rst.roles import set_classes as _du_set_classes
    _du_set_classes(options)
    return _du_nodes.reference(rawtext, linktext, refuri=linkurl,
                               **options)

_cache = [False,None]
def load_sbpkgs( app ):
    if not _cache[0]:
        _cache[1] = _actual_load_sbpkgs( app )
        _cache[0] = True
    return _cache[1]

def _actual_load_sbpkgs( app ):
    try:
        bundles = app.config.simplebuild_pkgbundles
        if not bundles:
            raise AttributeError
    except AttributeError as e:
        raise ValueError('simplebuild_pkgbundles configuration value'
                         ' is not set (%s)' % str(e))

    from .pkgutils import find_pkg_dirs_under_basedir as _findpkgs
    errors = []
    pkgs = {}
    def _errfct( msg ):
        errors.append( msg )
    for n,( pkgroot, urlbase ) in bundles.items():
        assert ( pkgroot / 'simplebuild.cfg' ).is_file()
        for p in _findpkgs( pkgroot, error_fct = _errfct ):
            if errors:
                break
            assert ( p / 'pkg.info' ).is_file()
            if p.name in pkgs:
                _errfct('Duplicate package name: "%s"'%p.name)
                break
            url = urlbase + '/' + str( p.relative_to(pkgroot) )
            pkgs[ p.name ] = { 'name' : p.name,
                               'pkgdir_local' : p,
                               'pkgdir_url' : url }
        if errors:
            break
    return dict( error_msg = errors[0] if errors else None,
                 pkgs = None if errors else pkgs )

