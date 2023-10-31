from . import conf
from . import utils
import os
splitext = os.path.splitext

langs = set(conf.lang_extensions.keys())

srcext2lang={}
hdrext2lang={}
for lang,exts in conf.lang_extensions.items():
    for hext in exts[0]:
        assert hext not in hdrext2lang
        hdrext2lang['.'+hext]=lang
    for sext in exts[1]:
        assert sext not in srcext2lang
        srcext2lang['.'+sext]=lang

assert set(srcext2lang.keys()).isdisjoint(set(hdrext2lang.keys()))

#todo: use a regexp? (see includes.py for an example)
_header_extensions=set(hdrext2lang.keys())
def headers_in_dir(d):
    return set(utils.listfiles(d,filterfnc=lambda f: splitext(f)[1] in _header_extensions,
                               error_on_no_match=False,ignore_logs=True))
