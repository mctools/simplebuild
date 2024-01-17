#This will remove any sb function defined by first redeclaring such a function
#(in case it was somehow already removed), then unset. It will also
#--env-unsetup any active sb project:
sb()
{
    true
}
unset -f sb
eval "$(unwrapped_simplebuild --env-unsetup)" 2>/dev/null || true
