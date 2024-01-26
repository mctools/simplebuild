#!/bin/bash
set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"
ruff "${REPOROOT_DIR}"/doc/source/conf.py
ruff --ignore E741 "${REPOROOT_DIR}"/src/_simple_build_system/*py
ruff "${REPOROOT_DIR}"/src/_simple_build_system/data/pkgs-core/*/python/*py
