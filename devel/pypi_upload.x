#!/bin/bash
set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"
set -x
cd "${REPOROOT_DIR}"
test -f "./pyproject.toml"
test -f "./simplebuild_redirect.cfg"
if [ -z "$(git status --porcelain --ignored)" ]; then
    python3 -mbuild
    twine upload dist/*
else
    echo "Error: git directory not clean (as per 'git status --porcelain --ignored')"
    exit 1
fi
