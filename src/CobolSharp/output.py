# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from contextlib import contextmanager

class Outputter(object):
    def __init__(self):
        self.link_prefix = ''

        self._indent = 0
        self._first_line_after_indent = False
        self._last_line_was_empty = False

    @contextmanager
    def indent(self):
        self.inc_indent()
        yield
        self.dec_indent()

    def inc_indent(self):
        self._indent += 1
        self._first_line_after_indent = True

    def dec_indent(self):
        self._indent -= 1

    def anchor(self, label):
        pass

    def line(self, text='', source=None, ref_para=None, ref_section=None, link=None):
        if not text:
            if self._last_line_was_empty or self._first_line_after_indent:
                return
            self._last_line_was_empty = True
        else:
            self._first_line_after_indent = False
            self._last_line_was_empty = False

        self._output_line(str(text), source, ref_para, ref_section, link)

    def _output_line(self, text, source, ref_para, ref_section, link):
        raise NotImplementedError()


class TextOutputter(Outputter):
    """Output formatted code as a text source file.
    """

    INDENT_SPACES = 4
    LINK_COLUMN = 60

    def __init__(self, output_file):
        super(TextOutputter, self).__init__()
        self._file = output_file

    def _output_line(self, text, source, ref_para, ref_section, link):
        self._file.write(' ' * self.INDENT_SPACES * self._indent)
        self._file.write(text)

        refs = []

        if source:
            refs.append('@{}'.format(source.from_line))

        if ref_para and ref_para.name:
            refs.append(ref_para.name)

        if ref_section:
            refs.append('{} section'.format(ref_section.name))

        if refs:
            w = self.INDENT_SPACES * self._indent + len(str(text))
            if w < self.LINK_COLUMN:
                self._file.write(' ' * (self.LINK_COLUMN - w))

            self._file.write('{}{}'.format(self.link_prefix, ', '.join(refs)))

        self._file.write('\n')


