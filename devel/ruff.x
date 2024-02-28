#!/bin/bash
set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"
PDATA="${REPOROOT_DIR}/src/_simple_build_system/data"
ruff check "${REPOROOT_DIR}"/doc/source/conf.py
ruff check --ignore E741 "${REPOROOT_DIR}"/src/_simple_build_system/*py
ruff check "${PDATA}/pkgs-core"/*/python/*py

ruff check "${PDATA}"/pkgs-core/Core/scripts/cmakebuildtype
ruff check "${PDATA}"/pkgs-core/Core/scripts/extdeps
ruff check "${PDATA}"/pkgs-core/Core/scripts/queryenv
ruff check "${PDATA}"/pkgs-core/Core/scripts/reflogupdate
ruff check "${PDATA}"/pkgs-core_val/CoreTests/scripts/testnodostxt
