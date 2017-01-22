# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from .structure import *
from .syntax import *
from .output import Line


class Pythonish(object):
    file_suffix = 'py'

    open_block = None
    close_block = None
    empty_block_placeholder = 'pass'

    comment_format = '# {}'.format
    method_format = 'def {}():'.format
    if_format = 'if {}:'.format
    else_if_format = 'elif {}:'.format
    else_text = 'else:'
    while_format = 'while {}:'.format
    forever_text = 'while True:'
    label_format = '<<{}>>'.format  # Ada syntax, "lacking" labels in python
    goto_format = 'goto {}'.format
    return_text = 'return'
    break_text = 'break'
    continue_text = 'continue'
    statement_format = '{}'.format

    @staticmethod
    def condition_format(condition):
        return str(condition)


class CSharpish(object):
    file_suffix = 'cs'

    open_block = '{'
    close_block = '}'
    empty_block_placeholder = None

    comment_format = '// {}'.format
    method_format = 'void {}()'.format
    if_format = 'if ({})'.format
    else_if_format = 'else if ({})'.format
    else_text = 'else'
    while_format = 'while ({})'.format
    forever_text = 'while (true)'
    label_format = '{}:'.format
    goto_format = 'goto {};'.format
    return_text = 'return;'
    break_text = 'break;'
    continue_text = 'continue;'
    statement_format = '{};'.format

    @staticmethod
    def condition_format(condition):
        if condition.inverted:
            return '!({})'.format(condition.source)
        else:
            return str(condition.source)


class CodeFormatter(object):
    def __init__(self, output, language):
        self._output = output
        self._lang = language

    def format_method(self, method):
        self._output.comment(method.cobol_section.comment)

        line = Line(self._lang.method_format(method.cobol_section.name),
                    href_section=method.cobol_section,
                    anchor='func.{}'.format(method.cobol_section.name),
                    xref_stmts=method.cobol_section.xref_stmts)

        with self._output.block(line):
            self.format_block(method.block)

            self._output += Line()


    def format_block(self, block):
        if self._lang.open_block:
            self._output += Line(self._lang.open_block)

        with self._output.indent():
            if not block.stmts and self._lang.empty_block_placeholder:
                self._output += Line(self._lang.empty_block_placeholder)

            for stmt in block.stmts:
                if isinstance(stmt, If):
                    self._format_if(stmt)

                elif isinstance(stmt, GotoLabel):
                    self._output.dec_indent()
                    self._output += Line()
                    self._output += Line(self._lang.label_format(stmt.name),
                                         href_para=stmt.cobol_para,
                                         anchor='label.{}'.format(stmt.name))
                    self._output.inc_indent()

                elif isinstance(stmt, Goto):
                    self._output += Line(self._lang.goto_format(stmt.label.name),
                                         href_output='label.{}'.format(stmt.label.name),
                                         href_para=stmt.label.cobol_para)
                    self._output += Line()

                elif isinstance(stmt, Return):
                    self._output += Line(self._lang.return_text)
                    self._output += Line()

                elif isinstance(stmt, While):
                    self._format_while(stmt)

                elif isinstance(stmt, Forever):
                    self._format_forever(stmt)

                elif isinstance(stmt, Break):
                    self._output += Line(self._lang.break_text)

                elif isinstance(stmt, Continue):
                    self._output += Line(self._lang.continue_text)

                elif isinstance(stmt, PerformSectionStatement):
                    self._output.comment(stmt.comment)
                    self._output += Line(self._lang.statement_format(stmt.source), source=stmt.source,
                                         href_output='func.{}'.format(stmt.section_name))

                elif isinstance(stmt, CobolStatement):
                    self._output.comment(stmt.comment)
                    self._output += Line(self._lang.statement_format(stmt.source),
                                         source=stmt.source)

                else:
                    assert False, 'unknown statement: {}'.format(repr(stmt))

        if self._lang.close_block:
            self._output += Line(self._lang.close_block)


    def _format_if(self, stmt):
        self._output += Line()
        self._output.comment(stmt.cobol_stmt.comment)

        cond = self._lang.condition_format(stmt.condition)
        line = Line(self._lang.if_format(cond),
                    source=stmt.condition.source)

        with self._output.block(line):
            self.format_block(stmt.then_block)

        while len(stmt.else_block.stmts) == 1 and isinstance(stmt.else_block.stmts[0], If):
            stmt = stmt.else_block.stmts[0]
            self._output.comment(stmt.cobol_stmt.comment)

            cond = self._lang.condition_format(stmt.condition)
            line = Line(self._lang.else_if_format(cond),
                        source=stmt.condition.source)

            with self._output.block(line):
                self.format_block(stmt.then_block)

        if stmt.else_block.stmts:
            with self._output.block(Line(self._lang.else_text)):
                self.format_block(stmt.else_block)

        self._output += Line()


    def _format_while(self, stmt):
        self._output += Line()
        self._output.comment(stmt.cobol_para.comment)

        cond = self._lang.condition_format(stmt.condition)
        line = Line(self._lang.while_format(cond),
                    source=stmt.cobol_branch_stmt.condition.source,
                    href_para=stmt.cobol_para)

        with self._output.block(line):
            self.format_block(stmt.block)

        self._output += Line()

    def _format_forever(self, stmt):
        self._output += Line()
        self._output.comment(stmt.cobol_para.comment)

        line = Line(self._lang.forever_text, href_para=stmt.cobol_para)
        with self._output.block(line):
            self.format_block(stmt.block)

        self._output += Line()

