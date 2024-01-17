
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


#test sb is a function:
testisfunction sb
#deactivation should remove the function again:
. "${SBTEST_SHELLSNIPPET_DEACTIVATE}"
testisnotfunction sb

echo "All good"
