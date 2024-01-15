#!/usr/bin/env bash
set -eu
TMP_THISDIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. "${TMP_THISDIR}/../resources/shellrc_snippet.sh"
"$@"
