# If you define the following function in your shell's login script
# (e.g. ~/.bashrc, ~/.bash_profile, ~/.zshrc, etc.) you will not have to
# manually invoke eval "$(sb --env-setup)" after building with simplebuild.
#
# The code below has been tested with a variety of modern shells, and even works
# in "set -eu" mode. In some shells (ksh) it can leak the local variables _sb_*
# variables.

sb()
{
    #Never intercept --env-[un]setup (which may be combined with -d/-r/-g/-x):
    case " $* " in *' --env-'* ) unwrapped_simplebuild "$@"; return ;; esac
    #Try with local vars (fails in ksh without "function sb{}" variant):
    declare _sb_ec 2>/dev/null || local _sb_ec 2>/dev/null || true
    #Actually perform wrapped call:
    unwrapped_simplebuild "$@" && _sb_ec=0 || _sb_ec=$?
    if [ ${_sb_ec} -eq 0 -o ${_sb_ec} -eq 73 ]; then
        #73 means build ok but tests failed, so setup env for both 0 & 73:
        eval "$(unwrapped_simplebuild --env-setup-after-build "$@")"
    fi
    return $_sb_ec
}
