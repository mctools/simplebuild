# We want to create XML in "JUNIT format". Apart from a few xml escaping
# functions, we do this manually since it is almost trivial.

import pathlib
from xml.sax.saxutils import escape as xml_escape_general_data
from xml.sax.saxutils import quoteattr as xml_escape_attribute_data

class Test:

    def __init__( self, cmdname, pkgname, time_elapsed_seconds ):
        self.__cmdname = cmdname
        self.__pkgname = pkgname
        self.__time_elapsed_seconds = time_elapsed_seconds
        self.__failure = None

    def time_elapsed_seconds( self ):
        return self.__time_elapsed_seconds

    def is_failure( self ):
        return self.__failure is not None

    def set_run_failure( self, logfile ):
        self.__failure = ( 'runfail', logfile )

    def set_reflog_failure( self, logdiff_file ):
        self.__failure = ( 'reflogfail', logdiff_file )

    def __readsafe( self, fn):
        s = pathlib.Path(fn).read_bytes()
        s = s.decode('utf-8','backslashreplace')
        return s if len(s)<11000 else (s[0:5000]+"\n<<<skipping to the ending>>>\n"+ s[-5000:] +"\n<<<output exceeds limit for inclusion here>>>")

    def _generate_xml(self):
        metadata = f'name={xml_escape_attribute_data(self.__cmdname)} {_fmt_time_attribute(self.__time_elapsed_seconds)} classname={xml_escape_attribute_data(self.__pkgname)}'
        if self.__failure is None:
            yield f'    <testcase {metadata} />'
        else:
            s = self.__readsafe(self.__failure[1])
            yield f'    <testcase {metadata}>'
            if self.__failure[0]=='runfail':
                s = s or '<Command gave no output>'
                msg = 'Execution failed'
            else:
                s = s or '<Diff mysteriously missing>;'
                msg = 'Output differs from reference'
            for line in f'      <failure type="failure" message={xml_escape_attribute_data(msg)}>{xml_escape_general_data(s)}</failure>'.splitlines():
                yield line
            yield '    </testcase>'

class TestXMLWriter:

    def __init__(self):
        self.__tests = []

    def add_test( self, test ):
        assert isinstance( test, Test )
        self.__tests.append( test )

    def generate_xml(self):
        ntests = len(self.__tests)
        nfailures = sum(1 for t in self.__tests if t.is_failure())
        time_sum = float(sum(t.time_elapsed_seconds() for t in self.__tests))

        yield f'<testsuites failures="{nfailures}" errors="0" tests="{ntests}" disabled="0" {_fmt_time_attribute(time_sum)}>'
        yield f'  <testsuite name="simplebuild-tests" disabled="0" failures="{nfailures}" errors="0" skipped="0" time="{time_sum}" tests="{ntests}">'
        for t in self.__tests:
            for line in t._generate_xml():
                yield line
        yield '  </testsuite>'
        yield '</testsuites>'

def _fmt_time_attribute( time_seconds ):
    return 'time=%s'%xml_escape_attribute_data('%g'%time_seconds)
