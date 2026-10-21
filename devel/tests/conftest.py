# The pytest based test suite is in the suite/ subdirectory. The other test
# scripts in this directory are invoked directly (see the CI workflows), and
# must not be collected by pytest (but they are also invoked by the test suite
# itself).
collect_ignore = [ 'test_build_variants.py' ]
