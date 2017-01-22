# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import os
from contextlib import contextmanager
from jinja2 import Environment, PackageLoader
from pkg_resources import get_distribution

class Outputter(object):
    INDENT_SPACES = 4

    def __init__(self, language):
        self._lang = language
        self._lineno = 0
        self._indent = 0
        self._first_line_after_indent = False
        self._pending_empty_line = False

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
        self._pending_empty_line = False

    def dec_indent(self):
        self._indent -= 1
        self._first_line_after_indent = False
        self._pending_empty_line = False


    @contextmanager
    def block(self, line):
        self.start_block(line)
        yield
        self.end_block()

    def start_block(self, line):
        self += line

    def end_block(self):
        pass


    def line(self, line=None):
        if not line or not line.text:
            if not self._first_line_after_indent:
                self._pending_empty_line = True
            return

        if self._pending_empty_line:
            self._do_output(Line())
            self._pending_empty_line = False

        self._first_line_after_indent = False
        self._do_output(line)


    def _do_output(self, line):
        self._lineno += 1
        line.number = self._lineno
        line.indent = self._indent
        self._output_line(line)


    def __iadd__(self, line):
        self.line(line)
        return self


    def comment(self, comment):
        if not comment:
            return

        self += Line()
        for text in comment.split('\n'):
            self += Line(self._lang.comment_format(text), comment=True)


    def _output_line(self, line):
        raise NotImplementedError()


class TextOutputter(Outputter):
    """Output formatted code as a text source file.
    """

    LINK_COLUMN = 60

    def __init__(self, output_file, language):
        super(TextOutputter, self).__init__(language)
        self._file = output_file

    def _output_line(self, line):
        indent = ' ' * self.INDENT_SPACES * line.indent

        self._file.write(indent)
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

            self._file.write(self._lang.comment_format(', '.join(refs)))

        self._file.write('\n')

        if line.xref_stmts:
            self._file.write('{}{}\n'.format(indent, self._lang.comment_format('References')))
            for stmt in line.xref_stmts:
                ref = '{:6d}: {}'.format(stmt.source.from_line, stmt.sentence.para.section.name)
                self._file.write('{}{} \n'.format(indent, self._lang.comment_format(ref)))


class HtmlOutputter(Outputter):
    """Output formatted code together with original Cobol as an HTML page.
    """

    def __init__(self, cobol_program, output_file, language):
        super(HtmlOutputter, self).__init__(language)
        self._file = output_file
        self._program = cobol_program

        self._cobol_lines = [CobolLine(i + 1, line)
                             for i, line
                             in enumerate(cobol_program.source.text.split('\n'))]

        self._items = []
        self._blocks = []


    def close(self):
        template = template_env.get_template('main.html')
        template.stream(
            program_path=os.path.basename(self._program.path),
            cobol_lines=self._cobol_lines,
            items=self._items,
            comment_format=self._lang.comment_format,
            bottom_fold_button=not not self._lang.close_block,
            version=get_distribution('cobolsharp').version,

            # Needed for template logic
            isinstance=isinstance,
            Line=Line,
            StartBlock=StartBlock,
            EndBlock=EndBlock,
        ).dump(self._file)

        self._cobol_lines = None
        self._items = None


    def start_block(self, line):
        block = StartBlock(line)
        self._items.append(block)
        self._blocks.append(block)
        self += line

    def end_block(self):
        start = self._blocks.pop()

        size = self._lineno - start.line.number
        if size < 5:
            start.suppress = True
        else:
            start.line.first_in_block = True

        self._items.append(EndBlock(start))


    def _output_line(self, line):
        self._items.append(line)

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


class Line(object):
    def __init__(self, text='', source=None, href_para=None, href_section=None,
             href_output=None, anchor=None, comment=False, xref_stmts=None):
        self.number = 0
        self.indent = 0
        self.first_in_block = False
        self.text = str(text)
        self.source = source
        self.href_para = href_para
        self.href_section = href_section
        self.href_output = href_output
        self.anchor = anchor
        self.comment = comment
        self.xref_stmts = xref_stmts


class StartBlock(object):
    def __init__(self, line):
        self.line = line
        self.suppress = False


class EndBlock(object):
    def __init__(self, start):
        self.start = start


def filter_code_span_class(line):
    if not line.text:
        return ''

    if line.comment:
        return 'comment'
    
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
template_env.filters['code_span.class'] = filter_code_span_class
template_env.filters['output_line.href'] = filter_output_line_href
template_env.filters['cobol_line.class'] = filter_cobol_line_class
template_env.filters['cobol_line.level'] = filter_cobol_line_level
template_env.filters['cobol_line.anchor'] = filter_cobol_line_anchor
template_env.filters['cobol_line.href'] = filter_cobol_line_href

