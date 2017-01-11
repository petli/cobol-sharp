# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from contextlib import contextmanager
from jinja2 import Environment, PackageLoader

class Outputter(object):
    INDENT_SPACES = 4

    def __init__(self):
        self.link_prefix = ''

        self._lineno = 0
        self._indent = 0
        self._first_line_after_indent = False
        self._last_line_was_empty = False

    def close(self):
        pass

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

    def line(self, text='', source=None, href_para=None, href_section=None,
             href_other=None, anchor=None):
        text = str(text)

        if not text:
            if self._last_line_was_empty or self._first_line_after_indent:
                return
            self._last_line_was_empty = True
        else:
            self._first_line_after_indent = False
            self._last_line_was_empty = False

        self._lineno += 1
        self._output_line(OutputLine(self._lineno, self._indent, text,
                                     source, href_para, href_section, href_other, anchor))

    def _output_line(self, line):
        raise NotImplementedError()


class TextOutputter(Outputter):
    """Output formatted code as a text source file.
    """

    LINK_COLUMN = 60

    def __init__(self, output_file):
        super(TextOutputter, self).__init__()
        self._file = output_file

    def _output_line(self, line):
        self._file.write(' ' * self.INDENT_SPACES * line.indent)
        self._file.write(line.text)

        refs = []

        if line.source:
            refs.append('@{}'.format(line.source.from_line))

        if line.href_para and line.href_para.name:
            refs.append(line.href_para.name)

        if line.href_section:
            refs.append('{} section'.format(line.href_section.name))

        if refs:
            w = self.INDENT_SPACES * line.indent + len(str(line.text))
            if w < self.LINK_COLUMN:
                self._file.write(' ' * (self.LINK_COLUMN - w))

            self._file.write('{}{}'.format(self.link_prefix, ', '.join(refs)))

        self._file.write('\n')


class HtmlOutputter(Outputter):
    """Output formatted code together with original Cobol as an HTML page.
    """

    def __init__(self, cobol_program, output_file):
        super(HtmlOutputter, self).__init__()
        self._file = output_file
        self._program = cobol_program

        self._cobol_lines = [CobolLine(i + 1, line)
                             for i, line
                             in enumerate(cobol_program.source.text.split('\n'))]

        self._output_lines = []


    def close(self):
        template = template_env.get_template('main.html')
        template.stream(cobol_lines=self._cobol_lines,
                        output_lines=self._output_lines).dump(self._file)

        self._cobol_lines = None
        self._output_lines = None


    def _output_line(self, line):
        self._output_lines.append(line)

        # Cross-reference usages
        if line.source:
            for i in range(line.source.from_line - 1, line.source.to_line):
                cobol_line = self._cobol_lines[i]
                cobol_line.used = True
                cobol_line.output_line = line

        if line.href_section:
            cobol_line = self._cobol_lines[line.href_section.source.from_line - 1]
            cobol_line.used = True
            cobol_line.section = line.href_section
            cobol_line.output_line = line

        if line.href_para:
            cobol_line = self._cobol_lines[line.href_para.source.from_line - 1]
            cobol_line.used = True
            cobol_line.para = line.href_para
            cobol_line.output_line = line


def link(link_type, link_id):
    # TODO: clean up link_id, although the cobol syntax rules should
    # ensure that all IDs are safe in an HTML attribute
    return '{}.{}'.format(link_type, link_id)


class OutputLine(object):
    def __init__(self, number, indent, text, source, href_para, href_section, href_other, anchor):
        self.number = number
        self.indent = indent
        self.text = text
        self.source = source
        self.href_para = href_para
        self.href_section = href_section
        self.href_other = href_other
        self.anchor = anchor


def filter_output_line_class(line):
    if not line.text:
        return ''

    return 'level{}'.format(line.indent % 8)


def filter_output_line_href(line):
    if line.href_section:
        return link('section', line.href_section.name)

    if line.href_para:
        return link('para', line.href_para.name)

    if line.source:
        return link('cobol', line.source.from_line)

    return ''


class CobolLine(object):
    def __init__(self, number, text):
        self.number = number
        self.text = text
        code = text.lstrip()
        self.whitespace = text[:len(text) - len(code)]
        self.code = code.rstrip()
        if not self.code:
            self.whitespace = ''
        self.used = False
        self.output_line = None
        self.para = None
        self.section = None


def filter_cobol_line_class(line):
    if not line.used:
        return 'unused'

    return ''


def filter_cobol_line_level(line):
    if not line.used:
        return ''

    return 'level{}'.format(line.output_line.indent % 8)


def filter_cobol_line_anchor(line):
    if line.para:
        return link('para', line.para.name)

    if line.section:
        return link('section', line.section.name)

    return ''


def filter_cobol_line_href(line):
    if line.section:
        return link('func', line.section.name)

    if line.output_line:
        return link('output', line.output_line.number)

    return ''


template_env = Environment(loader=PackageLoader('CobolSharp', 'templates'))
template_env.filters['output_line.class'] = filter_output_line_class
template_env.filters['output_line.href'] = filter_output_line_href
template_env.filters['cobol_line.class'] = filter_cobol_line_class
template_env.filters['cobol_line.level'] = filter_cobol_line_level
template_env.filters['cobol_line.anchor'] = filter_cobol_line_anchor
template_env.filters['cobol_line.href'] = filter_cobol_line_href

