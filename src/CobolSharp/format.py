# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from .structure import *
from .syntax import *

class PythonishFormatter(object):
    def __init__(self, output):
        self._output = output
        output.comment_prefix = '#'

    def format_method(self, method):
        self._output.comment(method.cobol_section.comment)
        self._output.line('def {}():'.format(method.cobol_section.name),
                          href_section=method.cobol_section,
                          anchor='func.{}'.format(method.cobol_section.name))

        with self._output.indent():
            self.format_block(method.block)

        self._output.line()


    def format_block(self, block):
        if not block.stmts:
            self._output.line('pass')
            return

        for stmt in block.stmts:
            if isinstance(stmt, If):
                self._output.line()
                self._output.comment(stmt.cobol_stmt.comment)
                self._output.line('if {}:'.format(stmt.condition),
                                  source=stmt.condition.source)

                with self._output.indent():
                    self.format_block(stmt.then_block)

                while len(stmt.else_block.stmts) == 1 and isinstance(stmt.else_block.stmts[0], If):
                    stmt = stmt.else_block.stmts[0]
                    self._output.line('elif {}:'.format(stmt.condition),
                                      source=stmt.condition.source)
                    with self._output.indent():
                        self.format_block(stmt.then_block)

                if stmt.else_block.stmts:
                    self._output.line('else:')
                    with self._output.indent():
                        self.format_block(stmt.else_block)

                self._output.line()

            elif isinstance(stmt, GotoLabel):
                # Borrow label syntax from ada
                self._output.line()
                self._output.line('<<<{}>>>'.format(stmt.name),
                                  href_para=stmt.cobol_para,
                                  anchor='label.{}'.format(stmt.name))

            elif isinstance(stmt, Goto):
                self._output.line('goto {}'.format(stmt.label.name),
                                  href_other='label.{}'.format(stmt.label.name),
                                  href_para=stmt.label.cobol_para)
                self._output.line()

            elif isinstance(stmt, Return):
                self._output.line('return')
                self._output.line()

            elif isinstance(stmt, While):
                self._output.line()
                self._output.comment(stmt.cobol_para.comment)
                self._output.line('while {}:'.format(stmt.condition),
                                  source=stmt.cobol_branch_stmt.condition.source,
                                  href_para=stmt.cobol_para)

                with self._output.indent():
                    self.format_block(stmt.block)

                self._output.line()

            elif isinstance(stmt, Forever):
                self._output.line()
                self._output.comment(stmt.cobol_para.comment)
                self._output.line('while True:', href_para=stmt.cobol_para)
                with self._output.indent():
                    self.format_block(stmt.block)
                self._output.line()

            elif isinstance(stmt, Break):
                self._output.line('break')

            elif isinstance(stmt, Continue):
                self._output.line('continue')

            elif isinstance(stmt, CobolStatement):
                self._output.comment(stmt.comment)
                self._output.line(stmt.source, source=stmt.source)

            else:
                assert False, 'unkonwn statement: {}'.format(repr(stmt))
