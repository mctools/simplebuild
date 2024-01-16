#!/bin/bash
set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"
set -x
cd "${REPOROOT_DIR}/doc"
test -f source/index.rst
test -f source/conf.py
make clean
mkdir -p build
sphinx-autobuild ./source/ ./build/html
