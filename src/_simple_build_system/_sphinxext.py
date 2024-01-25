
def setup(app):
    """Install the plugin."""
    from ._determine_version import determine_version
    version = determine_version()

    app.add_role('sbpkg', sbpkg_role)
    app.add_config_value('simplebuild_pkgbundles', None, 'env')
    return { 'version' : version }

def sbpkg_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    """Link to the source code of a given simplebuild package."""

    app = inliner.document.settings.env.app

    from .pkgutils import pkgname_valid_or_errmsg
    pkgname = text.strip()
    errmsg = pkgname_valid_or_errmsg( pkgname )
    if not errmsg:
        sbpkgs = load_sbpkgs(app)
        errmsg = sbpkgs['error_msg']
    if not errmsg:
        pkginfo = sbpkgs['pkgs'].get(pkgname)
        if not pkginfo:
            errmsg = 'Could not find package named "%s"'%pkgname
    if errmsg:
        msg = inliner.reporter.error(errmsg, line=lineno)
        return ( [inliner.problematic(rawtext, rawtext, msg)],
                 [msg] )
    node = _create_link_node(rawtext, app,
                             pkgname, pkginfo['pkgdir_url'], options)
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
        print (pkgroot)
        assert ( pkgroot / 'simplebuild.cfg' ).is_file()
        for p in _findpkgs( pkgroot, error_fct = _errfct ):
            if errors:
                break
            assert ( p / 'pkg.info' ).is_file()
            if p.name in pkgs:
                _errfct('Duplicate package name: "%s"'%p.name)
                break
            url = urlbase + '/' + str( p.relative_to(pkgroot) )
            if p.name=='G4Materials':
                print("TKTEST mapping:")
                print("  ",p)
                print("  ",p.relative_to(pkgroot))
                print("  ",url)
            pkgs[ p.name ] = { 'name' : p.name,
                               'pkgdir_local' : p,
                               'pkgdir_url' : url }
        if errors:
            break
    return dict( error_msg = errors[0] if errors else None,
                 pkgs = None if errors else pkgs )

