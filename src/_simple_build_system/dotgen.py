from . import conf

def dotgen(pkgloader,outfile,enabled_only=True):
    fh=open(outfile,'w')
    fh.write("digraph GG {\n")
    fh.write("node [\n")
    fh.write(" fontsize = \"12\"\n")
    fh.write("];\n")
    autodeps=conf.autodeps
    def sortfunc(p):
        n=len(p.direct_clients)+len(p.direct_deps_pkgnames)
        if p.name in autodeps:
            n=-1
        return (n,p.name)
    for p in sorted(pkgloader.pkgs,key=sortfunc):
        if p.name in autodeps:
            assert p.enabled
            fh.write('    "node_%s" [  label="%s" shape="doubleoctagon" ];\n'%(p.name,p.name))
        elif p.enabled:
            fh.write('    "node_%s" [  label="%s" shape="octagon" ];\n'%(p.name,p.name))
        else:
            if not enabled_only:
                fh.write('    "node_%s" [ fontcolor="gray" color="grey" label="%s" shape="octagon" ];\n'%(p.name,p.name))

    for p in pkgloader.pkgs:
        if enabled_only and not p.enabled:
            continue
        for pdname in p.direct_deps_pkgnames:
            if pdname not in autodeps:
                fh.write('    "node_%s" -> "node_%s"%s\n'%(p.name,pdname,'' if p.enabled else ' [ color="gray" ]'))
    fh.write("}\n")
    fh.close()
