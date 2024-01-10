#!/usr/bin/env bash
set -eu
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../../ && pwd )"
export SBTEST_SHELLSNIPPET="${REPOROOT_DIR}/resources/shellrc_snippet.sh"
test -f "${SBTEST_SHELLSNIPPET}"
TEST_SHELL_SNIPPET="${REPOROOT_DIR}/devel/tests/test_envsetup.sh"
test -f "${TEST_SHELL_SNIPPET}"

WORKDIR="$PWD/sbtesttmpdir_envsetup"
test ! -f "$WORKDIR"
test ! -d "$WORKDIR"
mkdir -p "$WORKDIR"


export tested=''

#important shells:
#  ksh (openbsd)
#  zsh (osx)
#  dash (ubuntu)
#  bash4 (most other modern linux)
#  bash3 (osx for people who switched to bash)
#  ash (??)
#  tcsh ?? freebsd
for i in bash dash zsh ksh ash; do
    export SBTEST_ALLOW_VAR_LEAK=0
    if [ "$i" == "ksh" ]; then
        export SBTEST_ALLOW_VAR_LEAK=1
    fi
    echo
    echo
    echo
    echo "========================================================"
    echo "==                   TESTING ${i}                     =="
    echo "========================================================"
    echo
    echo
    echo
    _shell_path=$(which $i 2>/dev/null) || _shell_path=''
    if [ "x${_shell_path}" == "x" ]; then
        echo "skipping %i (not available)"
        continue
    else
        "${_shell_path}" -c "echo testing $i"
        mkdir -p $WORKDIR/$i
        export SHELL="${_shell_path}"
        ( cd $WORKDIR/$i; "${_shell_path}" ${TEST_SHELL_SNIPPET} )
        export tested="${tested} ${i}"
    fi
done
echo
echo
echo
echo "========================================================"
echo "========================================================"
echo "========================================================"
echo
echo
echo
echo "All Ok. Tested shells: ${tested}"
