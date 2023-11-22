from . import envcfg as _envcfg
import sys as _sys

black = '\033[30m'
red = '\033[31m'
green = '\033[32m'
yellow = '\033[33m'
blue = '\033[34m'
magenta = '\033[35m'
cyan = '\033[36m'
lightgrey = '\033[37m'
darkgrey = '\033[90m'
lightred = '\033[91m'
lightgreen = '\033[92m'
lightyellow = '\033[93m'
lightblue = '\033[94m'
lightmagenta = '\033[95m'#pink
lightcyan = '\033[96m'
white = '\033[97m'
end = '\033[0m'

ok = lightgreen
bad = lightred
bldmsg_pkg = lightblue
bldmsg_objectfile = white
bldmsg_symlink = lightyellow
bldmsg_headers = lightyellow
bldmsg_shlib = lightmagenta
bldmsg_app = lightgreen
bldmsg_pymod = lightcyan
bldmsg_global = lightblue
bldmsg_notallselectwarn = lightyellow
grep_match = lightblue
grep_unmatch = magenta
inc_samepkg = blue
inc_samedir = lightblue
#inc_dynpkg = lightcyan
warnenvsetup = lightyellow

#allow users to modify colours by having stuff like "export SIMPLEBUILD_COLOR_FIX=bldmsg_symlink=red" in their environment:
cf = _envcfg.var.color_fix_code
if cf:
    exec(cf)

#Disable colours when output is redirected:
if not _sys.stdout.isatty():
    for cname in [c for c in dir() if not c[0]=='_']:
        exec('%s=""'%cname)


if __name__=='__main__':
    for cname in [c for c in dir() if not c[0]=='_' and not c=='end']:
        col=eval(cname)
        print(''.join([cname.ljust(20),' : ',str(col),cname,end]))

def bldcol(name):
    name='bldmsg_'+name
    assert name in globals()
    return '${COL_%s}'%name.upper()
bldend='${COL_END}'
