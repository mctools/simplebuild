from . import dirs
from . import utils

#Database for remembering package info between invocations.

def _new_db():
    return { 'pkg2timestamp' : {},#to detect when files changed
             'pkg2inc' : {},#keep track of provided public headers (populate at target __init__ stage)
             'pkg2parts' : {},#keep track of targets to the point where we can cleanup the install area when user removes files or dirs
             'pkg2reldir' : {},#keep track of pkg locations
             'pkg2runnables' : {},#Keep track of runnables (with cmdname, e.g. <pn>_bla_lala)
             'pkg2reflogs' : {},#Keep track of reference logs (e.g. <pn>_bla_lala.log)
             'pkg2directextdeps' : {},#list of extdep's directly used by package.
            }

def _load_db( dbfile ):
    #Load the db, but start from scratch if it is absent, broken, or has an
    #unexpected format (since all packages will then be reconfigured, this is
    #always safe):
    d = utils.pkl_load_or_none( dbfile )
    ref = _new_db()
    if not isinstance(d,dict) or any( not isinstance(d.get(k),dict) for k in ref ):
        return ref
    return d

#initial load:
dbfile=dirs.blddir / 'globdb.pkl'
db = _load_db( dbfile )

def save_to_file():
    utils.pkl_dump(db,dbfile)

def clear_pkg(pkgname):
    for k,v in db.items():
        if k.startswith('pkg2') and pkgname in v:
            del v[pkgname]
