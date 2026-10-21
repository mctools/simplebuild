#!/usr/bin/env bash

# Run the simplebuild test suite (in devel/tests/suite) with pytest. The tests
# use the simplebuild installation which is active in the current python
# environment, so for development work first install your local clone with:
#
#   python3 -m pip install -e ".[test]"
#
# Usage:
#
#   devel/runtests.x [quick] [pytest-args...]
#
# Without "quick", all tests are run (tests requiring missing features like
# shells, cppcheck, or NCrystal are skipped). With "quick", only the fast unit
# tests are run. Other arguments are passed on to pytest, e.g.:
#
#   devel/runtests.x -k coreval        (only tests with "coreval" in the name)
#   devel/runtests.x -m shells         (only the shell tests)
#   devel/runtests.x -x -v             (verbose, stop at first failure)
#
# If pytest-xdist is installed, tests are run in parallel (disable with -n0).
#
# See devel/tests/suite/sbtestutils.py for environment variables which can be
# used to fine-tune the testing (mostly intended for CI).

set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"

PYTHON="${PYTHON:-python3}"
ARGS=()
if [ "${1:-}" == "quick" ]; then
    shift
    ARGS+=( -m unit )
fi
if "${PYTHON}" -c 'import xdist' 2>/dev/null; then
    #NB: --dist loadfile keeps tests in the same file in the same process,
    #which is needed for classes of tests which must run in order:
    ARGS+=( -n auto --dist loadfile )
fi
cd "${REPOROOT_DIR}"
exec "${PYTHON}" -m pytest "${ARGS[@]+"${ARGS[@]}"}" "$@"
