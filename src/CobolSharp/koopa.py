# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

"""Parse Cobol code using koopa.
"""


# java -cp ~/src/koopa-r356.jar -Dkoopa.xml.include_positioning=true koopa.app.cli.ToXml testsyntax.cbl /tmp/testsyntax.xml

import subprocess
import os
from pkg_resources import resource_filename
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

from .syntax import *

class ParserError(Exception): pass

def parse(source, java_binary = 'java'):
    """Parse Cobol code in 'source', which must be a text file-like object
    with a read() method or a string.

    Returns a Program object.
    """

    if hasattr(source, 'read'):
        code = source.read()
    elif isinstance(source, str):
        code = source
    else:
        raise TypeError('source must be a file-like object or a string')

    return ProgramParser(code, java_binary).program


class ProgramParser(object):
    KOOPA_JAR = 'data/koopa-r356.jar'

    def __init__(self, code, java_binary):
        self._code = code
        self._run_koopa(java_binary)
        self._parse()

    def _run_koopa(self, java_binary):
        source_file = None
        result_file = None

        try:
            source_file = NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.cbl', delete=False)
            source_file.write(self._code)
            source_file.close()

            # Just grab a temp file name for the results
            result_file = NamedTemporaryFile(mode='wb', suffix='.xml', delete=False)
            result_file.close()

            jar = resource_filename('CobolSharp', self.KOOPA_JAR)

            cmd = (java_binary, '-cp', jar, '-Dkoopa.xml.include_positioning=true',
                   'koopa.app.cli.ToXml', source_file.name, result_file.name)

            process = subprocess.Popen(cmd,
                                       stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       universal_newlines=True)

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise ParserError(stdout)

            self._tree = ET.parse(result_file.name)

        finally:
            pass
            if source_file:
                os.remove(source_file.name)
            if result_file:
                os.remove(result_file.name)


    def _parse(self):
        unit_el = self._tree.find('compilationGroup')
        proc_div_el = unit_el.find('.//procedureDivision')

        proc_div = ProcedureDivision(self._source(proc_div_el))

        self.program = Program(self._source(unit_el), proc_div)


    def _source(self, element):
        return Source(self._code,
                      int(element.get('from')) - 1,
                      int(element.get('to')) - 1,
                      int(element.get('from-line')) - 1,
                      int(element.get('to-line')) - 1,
                      int(element.get('from-column')) - 1,
                      int(element.get('to-column')) - 1)

