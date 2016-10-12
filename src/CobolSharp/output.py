# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

from contextlib import contextmanager

class Outputter(object):
    def __init__(self):
        self._indent = 0

    @contextmanager
    def indent(self):
        self.inc_indent()
        yield
        self.dec_indent()

    def inc_indent(self):
        self._indent += 1

    def dec_indent(self):
        self._indent -= 1

    def anchor(self, label):
        pass

    def line(self, text='', link=None):
        raise NotImplementedError()

class TextOutputter(Outputter):
    def __init__(self, output_file):
        super(TextOutputter, self).__init__()
        self._file = output_file
        self._last_line_was_empty = False

    def line(self, text='', link=None):
        if not text:
            if self._last_line_was_empty:
                return
            self._last_line_was_empty = True
        else:
            self._last_line_was_empty = False

        self._file.write('    ' * self._indent)
        self._file.write(str(text))
        if link is not None:
            self._file.write('    [{}]'.format(link))
        self._file.write('\n')


