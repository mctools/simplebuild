
#Invoke this script via test_envsetup_manyshells.x:

#Testing https://github.com/mctools/simplebuild/issues/33

export SIMPLEBUILD_CFG=
unset SIMPLEBUILD_CFG
export SIMPLEBUILD_CFG

eval "$(sb --env-unsetup)"
#set -eux in one go works in bash+dash but not zsh:
set -e
set -u
set -x

test -f "${SBTEST_SHELLSNIPPET}"
test -f "${SBTEST_SHELLSNIPPET_DEACTIVATE}"
test -f "${SBTEST_OLD_SHELLSNIPPET}"
WORKDIR="$PWD/sbproj"
test ! -f "$WORKDIR"
test ! -d "$WORKDIR"

testnoleaks()
{
    test -z "${_sb_realcmd:-}"
    if [ $SBTEST_ALLOW_VAR_LEAK -eq 0 ]; then
        test -z "${_sb_ec:-}"
    fi
}
testisfunction()
{
    pn="$1"
    if [ $SBTEST_HAS_TYPESETMINUSF -eq 1 ]; then
        EC=0
        typeset -f "$pn" > /dev/null || EC=$?
        return $EC
    else
        aa="$(type $pn)"
        bb="$pn is a shell function"
        if [ "x${aa}" = "x${bb}" ]; then
            return 0
        else
            return 1
        fi
    fi
}
testisnotfunction()
{
    EC=0
    testisfunction $1 || EC=$?
    if [ $EC -ne 0 ]; then
        return 0
    else
        return 1
    fi
}


. "${SBTEST_SHELLSNIPPET_DEACTIVATE}"
testisnotfunction sb

testnoleaks
mkdir -p "$WORKDIR"
cd "$WORKDIR"

. "${SBTEST_SHELLSNIPPET}"
testnoleaks
sb --init
testnoleaks
mkdir -p MyPkg/scripts
echo 'package()' > MyPkg/pkg.info
echo '#!/usr/bin/env python3' >  MyPkg/scripts/testbad
echo 'raise SystemExit(1)' >> MyPkg/scripts/testbad
chmod +x MyPkg/scripts/testbad
EC=0
sb --tests || EC=$?
testnoleaks
test $EC -eq 73
EC=0
which sb_mypkg_testbad || EC=$?
test $EC -eq 0
mkdir MyPkg/app_nocompile
echo 'this is not actually c++' > MyPkg/app_nocompile/main.cc
EC=0
sb || EC=$?
testnoleaks
test $EC -ne 0
test $EC -ne 73

#Build variants (-d/-r/-g/-x), for which the sb function must set up the
#environment after each build, depending only on the flags of that build:
rm -rf MyPkg/app_nocompile
echo "  extra_cflags = '-DSBTEST_DUMMY=1'" >> simplebuild.cfg
WORKDIR_REAL="$(cd "$WORKDIR" && pwd -P)"
checkprefix()
{
    _sbtest_expected="${WORKDIR_REAL}/simplebuild_cache/$1"
    if [ "${SBLD_INSTALL_PREFIX:-unset}" != "${_sbtest_expected}" ]; then
        echo "Unexpected SBLD_INSTALL_PREFIX=${SBLD_INSTALL_PREFIX:-unset}"
        echo "        (expected ${_sbtest_expected})"
        exit 1
    fi
}
checkcmd()
{
    test "$(command -v sb_mypkg_testbad)" \
         = "${SBLD_INSTALL_PREFIX}/scripts/sb_mypkg_testbad"
}
sb -q
testnoleaks
XF="$(ls simplebuild_cache | grep '^install_xf')"
HASH="${XF#install_xf}"
test -n "${HASH}"
checkprefix "install_xf${HASH}"
checkcmd
sb -q -x
testnoleaks
checkprefix install
checkcmd
sb -q -d
checkprefix "install_debug_xf${HASH}"
checkcmd
EC=0
sb -q -tdx || EC=$?
testnoleaks
test $EC -eq 73
checkprefix install_debug
checkcmd
sb -x -q -r
checkprefix install
checkcmd
sb -q
checkprefix "install_xf${HASH}"
checkcmd

#Explicit --env-setup with variant flags, which must not trigger a build:
test ! -d "simplebuild_cache/bld_reldbg_xf${HASH}"
eval "$(sb -g --env-setup)"
testnoleaks
checkprefix "install_reldbg_xf${HASH}"
test ! -d "simplebuild_cache/bld_reldbg_xf${HASH}"
eval "$(sb --env-setup -x)"
checkprefix install
checkcmd
eval "$(sb -d --env-setup)"
checkprefix "install_debug_xf${HASH}"
checkcmd
eval "$(sb --env-unsetup)"
testnoleaks
test -z "${SBLD_INSTALL_PREFIX:-}"
eval "$(sb --env-setup)"
checkprefix "install_xf${HASH}"
checkcmd

#The sb function from older simplebuild versions must give a clear error after
#a build (but no other output, since that is eval'ed):
eval "$(sb --env-unsetup)"
. "${SBTEST_OLD_SHELLSNIPPET}"
EC=0
sb -q 2> olderr.txt || EC=$?
testnoleaks
test $EC -eq 0
grep -q 'outdated version of the "sb" shell function' olderr.txt
test -z "${SBLD_INSTALL_PREFIX:-}"
. "${SBTEST_SHELLSNIPPET}"
testnoleaks
sb -q
checkprefix "install_xf${HASH}"
checkcmd

#test sb is a function:
testisfunction sb
#deactivation should remove the function again:
. "${SBTEST_SHELLSNIPPET_DEACTIVATE}"
testisnotfunction sb

echo "All good"
