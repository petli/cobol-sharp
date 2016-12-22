# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

from .structure import *
from .syntax import *

class PythonishFormatter(object):
    def __init__(self, output):
        self._output = output

    def format_method(self, method):
        self._output.line('def {}:'.format(method.cobol_section.name),
                          link='{} section'.format(method.cobol_section.name))

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
                self._output.line('if {}{}:'.format(
                    'not ' if stmt.invert_condition else '',
                    stmt.cobol_stmt.condition),
                                  link=stmt.cobol_stmt.source.from_line)

                with self._output.indent():
                    self.format_block(stmt.then_block)

                if stmt.else_block.stmts:
                    self._output.line('else:')
                    with self._output.indent():
                        self.format_block(stmt.else_block)

                self._output.line()

            elif isinstance(stmt, GotoLabel):
                link = None
                if stmt.cobol_para:
                    link = stmt.cobol_para.name

                # Borrow label syntax from ada
                self._output.line()
                self._output.anchor(stmt.name)
                self._output.line('<<<{}>>>'.format(stmt.name), link=link)

            elif isinstance(stmt, Goto):
                self._output.line('goto {}'.format(stmt.label.name), link=stmt.label.name)
                self._output.line()

            elif isinstance(stmt, Return):
                self._output.line('return')
                self._output.line()

            elif isinstance(stmt, While):
                self._output.line()
                self._output.line('while {}{}:'.format(
                    'not ' if stmt.invert_condition else '',
                    stmt.cobol_branch_stmt.condition))
                with self._output.indent():
                    self.format_block(stmt.block)
                self._output.line()

            elif isinstance(stmt, Forever):
                self._output.line()
                self._output.line('while True:')
                with self._output.indent():
                    self.format_block(stmt.block)
                self._output.line()

            elif isinstance(stmt, Break):
                self._output.line('break')

            elif isinstance(stmt, Continue):
                self._output.line('continue')

            elif isinstance(stmt, CobolStatement):
                self._output.line(stmt.source, link=stmt.source.from_line)

            else:
                assert False, 'unkonwn statement: {}'.format(repr(stmt))
