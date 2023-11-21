# If you define the following bash functions, you will not have to manually
# invoke eval "$(simplebuild --env-setup)" after building a project. Depending
# on your system and setup, the lines below should most likely be copied to
# either a file named ~/.bashrc or ~/.bash_profile (but other alternatives
# exists).

function simplebuild()
{
    real_simplebuild_cmd=$(which unwrapped_simplebuild 2>/dev/null) || ( echo "error: simplebuild not available" 1>&2 ; exit 1 )
    if [ $? == 0 -a "x${real_simplebuild_cmd}" != "x" ]; then
        "${real_simplebuild_cmd}" "$@" && eval "$(${real_simplebuild_cmd} --env-setup)"
    fi
    unset real_simplebuild_cmd
}
function sb()
{
    simplebuild "$@"
}
