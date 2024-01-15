#!/usr/bin/env bash
set -eu
TMP_THISDIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. "${TMP_THISDIR}/../resources/shellrc_snippet.sh"
#CMDLOGSTART
#PRETENDRUN: conda activate sbenv
echo "CMDPROMPT>mkdir sbverify"
mkdir sbverify
echo "CMDPROMPT>cd sbverify"
cd sbverify
echo "CMDPROMPT>sb --init core_val"
sb --init core_val
echo "CMDPROMPT>sb --tests"
sb --tests
