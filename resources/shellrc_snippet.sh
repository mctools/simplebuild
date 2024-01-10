# If you define the following function in your shell's login script
# (e.g. ~/.bashrc, ~/.bash_profile, ~/.zshrc, etc.) you will not have to
# manually invoke eval "$(sb --env-setup)" after building with simplebuild.
#
# The code below has been tested with a variety of modern shells, and even works
# in "set -eu" mode. In some shells (ksh) it can leak the local _sb_ec variable.

sb()
{
    #Try with local vars (fails in ksh without "function sb{}" variant):
    declare _sb_realcmd _sb_ec 2>/dev/null \
        || local _sb_realcmd _sb_ec 2>/dev/null || true
    _sb_realcmd=$(which unwrapped_simplebuild 2>/dev/null) \
        || ( echo "error: simplebuild not available" 1>&2 ; exit 1 )
    if [ $? -eq 0 -a "x${_sb_realcmd}" != "x" ]; then
        "${_sb_realcmd}" "$@" && _sb_ec=0 || _sb_ec=$?
        #73 means build ok but some tests failed.
        if [ ${_sb_ec} -eq 0 -o ${_sb_ec} -eq 73 ]; then
            eval "$(${_sb_realcmd} --env-setup-silent-fail)"
        else
            eval "$(${_sb_realcmd} --env-unsetup)"
        fi
        unset _sb_realcmd
        return $_sb_ec
    else
        unset _sb_realcmd
        return 1
    fi
}
