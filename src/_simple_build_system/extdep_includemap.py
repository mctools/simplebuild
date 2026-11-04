from _simple_build_system import utils
import re
_include_extractor = re.compile(b'^\\s*#\\s*include\\s'
                                b'*"\\s*(([a-zA-Z0-9_/.]+))\\s*"').match
def _get_raw_includes( path ):
    res = []
    for line in utils.include_candidate_lines( path ):
        v = _include_extractor(line)
        if v:
            res.append(v.groups()[1].decode('utf8'))
    return set(res)

def read_text_mapped_include_statements( path, includemap_list ):
    #Finds raw include statements in the input file, maps them according to the
    #include maps (a list of (extdepname,includemap) pairs), and produces fake
    #output with the resulting mapped output in fake '#include "..."' lines.
    #Also returns a dictionary with the origin, (rawinclude,extdepname), of each
    #mapped include. Lines with the sbld::nodep marker are ignored.
    raw_includes = []
    for line in utils.include_candidate_lines( path ):
        if b'sbld::nodep' in line:
            continue
        v = _include_extractor(line)
        if v:
            raw_includes.append(v.groups()[1].decode('utf8'))

    final = set()
    origins = {}
    for r in sorted(set(raw_includes)):
        for extdepname, m in includemap_list:
            mapped = m.get(r)
            if mapped:
                #Just take the first one:
                origins.setdefault( mapped, ( r, extdepname ) )
                r = mapped
                break
        final.add(r)
    return ''.join('#include "%s"\n'%e for e in final), origins
