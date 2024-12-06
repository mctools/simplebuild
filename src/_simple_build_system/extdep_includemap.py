from _simple_build_system import utils
import re
_include_extractor = re.compile(b'^\\s*#\\s*include\\s'
                                b'*"\\s*(([a-zA-Z0-9_/.]+))\\s*"').match
def _get_raw_includes( path ):
    #For efficiency, initial dig through file use grep command:
    ec,output=utils.run(['grep','.*#.*include.*"..*"',str(path.absolute())])
    if ec == 1:
        #grep exit code of 1 simply indicates no hits
        return set()
    elif ec!=0:
        raise RuntimeError('grep command failed')
    res = []
    for line in output.splitlines():
        v = _include_extractor(line)
        if v:
            res.append(v.groups()[1].decode('utf8'))
    return set(res)

def read_text_mapped_include_statements( path, includemap_list ):
    #Finds raw include statements in the input file, maps them according to the
    #include map, and produces fake output with the resulting mapped output in
    #fake '#include "..."' lines.
    #For efficiency, initially dig through file use grep command:
    ec,output=utils.run(['grep','.*#.*include.*"..*"',str(path.absolute())])
    if ec == 1:
        #grep exit code of 1 simply indicates no hits
        return ''
    elif ec!=0:
        raise RuntimeError('grep command failed')
    raw_includes = []
    for line in output.splitlines():
        v = _include_extractor(line)
        if v:
            raw_includes.append(v.groups()[1].decode('utf8'))

    final = set()
    for r in sorted(set(raw_includes)):
        for m in includemap_list:
            mapped = m.get(r)
            if mapped:
                #Just take the first one:
                r = mapped
                break
        final.add(r)
    return ''.join('#include "%s"\n'%e for e in final)
