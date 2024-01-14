#This will remove any sb function defined by first redeclaring such a function
#(in case it was already removed), then unset:
sb()
{
    true
}
unset -f sb
