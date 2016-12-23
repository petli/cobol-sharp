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

    def line(self, text='', link=None):
        if not text:
            if self._last_line_was_empty or self._first_line_after_indent:
                return
            self._last_line_was_empty = True
        else:
            self._first_line_after_indent = False
            self._last_line_was_empty = False

        self._output_line(str(text), link)

    def _output_line(self, text, link):
        raise NotImplementedError()


class TextOutputter(Outputter):
    INDENT_SPACES = 4
    LINK_COLUMN = 60

    def __init__(self, output_file):
        super(TextOutputter, self).__init__()
        self._file = output_file

    def _output_line(self, text, link):
        self._file.write(' ' * self.INDENT_SPACES * self._indent)
        self._file.write(text)

        if link is not None:
            w = self.INDENT_SPACES * self._indent + len(str(text))
            if w < self.LINK_COLUMN:
                self._file.write(' ' * (self.LINK_COLUMN - w))

            self._file.write('{}{}'.format(self.link_prefix, link))

        self._file.write('\n')


