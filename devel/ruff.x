#!/bin/bash
set -e
set -u
REPOROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && cd ../ && pwd )"
PDATA="${REPOROOT_DIR}/src/_simple_build_system/data"
OPTS="--select=W,E,F"

ruff check ${OPTS} --ignore E501 "${REPOROOT_DIR}"/doc/source/conf.py
ruff check ${OPTS} --ignore E501 "${REPOROOT_DIR}"/src/_simple_build_system/*py
ruff check ${OPTS} "${PDATA}/pkgs-core"/*/python/*py

ruff check ${OPTS} "${PDATA}"/pkgs-core/Core/scripts/extdeps
ruff check ${OPTS} "${PDATA}"/pkgs-core/Core/scripts/queryenv
ruff check ${OPTS} --ignore E501 "${PDATA}"/pkgs-core/Core/scripts/reflogupdate
ruff check ${OPTS} "${PDATA}"/pkgs-core_val/CoreTests/scripts/testnodostxt
