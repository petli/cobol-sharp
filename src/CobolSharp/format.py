# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from .structure import *
from .syntax import *
from .output import Line

class PythonishFormatter(object):
    def __init__(self, output):
        self._output = output
        output.comment_prefix = '#'

    def format_method(self, method):
        self._output.comment(method.cobol_section.comment)

        line = Line('def {}():'.format(method.cobol_section.name),
                    href_section=method.cobol_section,
                    anchor='func.{}'.format(method.cobol_section.name),
                    xref_stmts=method.cobol_section.xref_stmts)

        with self._output.block(line):
            with self._output.indent():
                self.format_block(method.block)

            self._output += Line()


    def format_block(self, block):
        if not block.stmts:
            self._output += Line('pass')
            return

        for stmt in block.stmts:
            if isinstance(stmt, If):
                self._output += Line()
                self._output.comment(stmt.cobol_stmt.comment)

                line = Line('if {}:'.format(stmt.condition),
                            source=stmt.condition.source)

                with self._output.block(line):
                    with self._output.indent():
                        self.format_block(stmt.then_block)

                while len(stmt.else_block.stmts) == 1 and isinstance(stmt.else_block.stmts[0], If):
                    stmt = stmt.else_block.stmts[0]
                    self._output.comment(stmt.cobol_stmt.comment)

                    line = Line('elif {}:'.format(stmt.condition),
                                source=stmt.condition.source)

                    with self._output.block(line):
                        with self._output.indent():
                            self.format_block(stmt.then_block)

                if stmt.else_block.stmts:
                    with self._output.block(Line('else:')):
                        with self._output.indent():
                            self.format_block(stmt.else_block)

                self._output += Line()

            elif isinstance(stmt, GotoLabel):
                # Borrow label syntax from ada
                self._output += Line()
                self._output += Line('<<<{}>>>'.format(stmt.name),
                                     href_para=stmt.cobol_para,
                                     anchor='label.{}'.format(stmt.name))

            elif isinstance(stmt, Goto):
                self._output += Line('goto {}'.format(stmt.label.name),
                                     href_output='label.{}'.format(stmt.label.name),
                                     href_para=stmt.label.cobol_para)
                self._output += Line()

            elif isinstance(stmt, Return):
                self._output += Line('return')
                self._output += Line()

            elif isinstance(stmt, While):
                self._output += Line()
                self._output.comment(stmt.cobol_para.comment)

                line = Line('while {}:'.format(stmt.condition),
                            source=stmt.cobol_branch_stmt.condition.source,
                            href_para=stmt.cobol_para)

                with self._output.block(line):
                    with self._output.indent():
                        self.format_block(stmt.block)

                self._output += Line()

            elif isinstance(stmt, Forever):
                self._output += Line()
                self._output.comment(stmt.cobol_para.comment)

                line = Line('while True:', href_para=stmt.cobol_para)
                with self._output.block(line):
                    with self._output.indent():
                        self.format_block(stmt.block)
                self._output += Line()

            elif isinstance(stmt, Break):
                self._output += Line('break')

            elif isinstance(stmt, Continue):
                self._output += Line('continue')

            elif isinstance(stmt, PerformSectionStatement):
                self._output.comment(stmt.comment)
                self._output += Line(stmt.source, source=stmt.source,
                                     href_output='func.{}'.format(stmt.section_name))

            elif isinstance(stmt, CobolStatement):
                self._output.comment(stmt.comment)
                self._output += Line(stmt.source, source=stmt.source)

            else:
                assert False, 'unkonwn statement: {}'.format(repr(stmt))
