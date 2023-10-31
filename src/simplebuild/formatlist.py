def formatlist(l,width,colour=None,indent_first='',indent_others='',nonetext='<none>'):
    from . import col
    #entries in input list are either in format (text,color) or simply
    #(text). colour will be used to override all colours (colour='' will turn
    #all colours off).
    out=['']
    i=0
    for entry in l:
        try:
            e,c = entry
        except ValueError:
            e=entry
            c=colour
        if colour is not None:
            c=colour
        if i>width:
            out+=['']
            i=0
        k=len(e)
        if c:
            e=c+e+col.end
        out[-1]+=' '+e if i else e
        i+=k
    if nonetext and out==['']:
        out=[nonetext]
    for i in range(len(out)):
        if indent_first and i==0:
            out[i]=indent_first+out[i]
        if indent_others and i>0:
            out[i]=indent_others+out[i]
    return out
