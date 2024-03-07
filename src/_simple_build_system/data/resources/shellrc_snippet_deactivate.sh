#This will remove any sb function defined by first redeclaring such a function
#(in case it was somehow already removed), then unset:
sb()
{
    true
}
unset -f sb

#We also unsetup any active simplebuild environment. However, if invoked as a
#conda deactivation script, CONDA_PREFIX/bin might have already been removed
#from the path, so we reinject it in that case:
if [ "${_SIMPLEBUILD_CURRENT_ENV:-x}" != "x" ]; then
    if [ "${CONDA_PREFIX:-x}" != "x" -a -f "${CONDA_PREFIX:-x}/bin/sb" ]; then
        eval "$(${CONDA_PREFIX}/bin/sb --env-unsetup 2>/dev/null)" 2>/dev/null || true
    else
        eval "$(sb --env-unsetup 2>/dev/null)" 2>/dev/null || true
    fi
fi
