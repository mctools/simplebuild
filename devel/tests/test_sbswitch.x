#!/bin/bash
set -eu

# Added this test to investigate issues (although could not reproduce the
# issues, the test seems like a good test to have).
#
# https://github.com/mctools/simplebuild/issues/57
# https://github.com/mctools/simplebuild/issues/39
# https://github.com/mctools/simplebuild/issues/38


REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../../ && pwd )"
WORKDIR="$PWD/tmpdir_testsbswitch"

. "${REPOROOT_DIR}/resources/shellrc_snippet_deactivate.sh"
. "${REPOROOT_DIR}/resources/shellrc_snippet.sh"

rm -rf "${WORKDIR}"
mkdir -p $WORKDIR
cd $WORKDIR
eval "$(sb --env-unsetup)"

P1="$WORKDIR/project1"
P2="$WORKDIR/project2"
mkdir "$P1" "$P2"

function verify_active() {
    test "$SBLD_INCLUDE_DIR" == "$1/install/include"
    test "$(which sb_core_finddata)" == "$1/install/scripts/sb_core_finddata"
}
function verify_no_active() {
    test "${SBLD_INCLUDE_DIR:-isunset}" == "isunset"
    test "${_SIMPLEBUILD_CURRENT_ENV:-isunset}" == "isunset"
}

(cd "$P1" && unwrapped_simplebuild --init core COMPACT)
(cd "$P2" && unwrapped_simplebuild --init core COMPACT)

verify_no_active

echo STEP1
cd "$P1"
export SBLD_DEVEL_TESTCMAKECFG_MODE=INVOKECMAKE
sb -q
verify_active "$P1/simplebuild_cache"

echo STEP2
cd "$P2"
export SBLD_DEVEL_TESTCMAKECFG_MODE=INVOKECMAKE
sb -q
verify_active "$P2/simplebuild_cache"

echo STEP3
cd "$P1"
export SBLD_DEVEL_TESTCMAKECFG_MODE=REUSE
sb -q
verify_active "$P1/simplebuild_cache"

echo STEP4
#export SIMPLEBUILD_CFG="${P2}/simplebuild.cfg"
cd "$P2"
export SBLD_DEVEL_TESTCMAKECFG_MODE=REUSE
sb -q
verify_active "$P2/simplebuild_cache"

echo STEP5

(cd "$P1" && rm -f simplebuild.cfg && unwrapped_simplebuild --init core COMPACT CACHEDIR::"$WORKDIR/project1_explicitcache")

echo STEP6
cd "$P1"
export SBLD_DEVEL_TESTCMAKECFG_MODE=INVOKECMAKE
sb -q
verify_active "$WORKDIR/project1_explicitcache"

echo STEP7
cd "$P1"
export SBLD_DEVEL_TESTCMAKECFG_MODE=REUSE
sb -q
verify_active "$WORKDIR/project1_explicitcache"

echo ALL OK
