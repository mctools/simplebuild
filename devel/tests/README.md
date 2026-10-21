# simplebuild tests

## The test suite

The pytest based test suite is in the `suite/` subdirectory. It tests the
simplebuild installation which is active in the current python environment,
so for development work, first install your local clone (with the test
dependencies) in editable mode:

```
python3 -m pip install -e ".[test]"
```

Then run the tests with:

```
devel/runtests.x         # all tests (in parallel if pytest-xdist is installed)
devel/runtests.x quick   # only the fast unit tests (a few seconds)
```

Extra arguments are passed on to pytest (e.g. `-k coreval`, `-m shells`,
`-x -v`). Plain `python3 -m pytest` from the repository root also works.

The tests are marked as `unit` (fast tests of the python code), `integration`
(invoking `sb`, `sbrun`, `sbenv`, etc. on temporary projects), or `shells`
(the `sb` shell function in various shells). Tests needing features which are
not available (e.g. a particular shell, `cppcheck`, or NCrystal) are skipped,
unless the feature is listed in the `SBTEST_REQUIRE` environment variable (see
`suite/sbtestutils.py` for this and other environment variables).

## Standalone test scripts

The other scripts in this directory are invoked directly by CI workflows, and
are also invoked by the test suite:

* `test_envsetup_manyshells.x` (and `test_envsetup.sh`): The `sb` shell
  function in various shells.
* `test_sbswitch.x`: Switching between projects with the `sb` shell function.
* `test_build_variants.py`: Build variants (extra flags, `-d/-r/-g/-x`, cache
  directory management).

## CI

The `all-tests` workflow runs the test suite in various environments (pip and
conda installations, Linux and macOS, many python versions and compilers), as
well as the standalone shell tests and the documentation build. All
workflows provide the logs of all their jobs as a single downloadable
tarball (the `all-ci-logs-*` artifact).
