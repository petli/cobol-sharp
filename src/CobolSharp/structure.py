# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

class _DummySource(object):
    """This is only used to enable sorting of Entry/Exit with CobolStatements."""
    def __init__(self, from_char):
        self.from_char = from_char

class _Entry(object):
    """Singleton used as the entry node in all graphs."""

    def __str__(self):
        return 'Entry'

    source = _DummySource(-1)

Entry = _Entry()


class _Exit(object):
    """Singleton used as the exit node in all graphs."""

    def __str__(self):
        return 'Exit'

    source = _DummySource(0x80000000)

Exit = _Exit()


class Branch(object):
    """A node that branches to then/else edges in BranchJoinGraph."""

    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source

    def __str__(self):
        return 'Branch {}'.format(self.stmt)


class Join(object):
    """A node where a number of edges join in BranchJoinGraph, but doesn't branch out again."""

    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source

    def __str__(self):
        return 'Join {}'.format(self.source.from_line)


class Loop(object):
    """Start of a loop in an AcyclicBranchGraph."""

    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source
        self.nodes = set()

    def __str__(self):
        return 'Loop {}'.format(self.source.from_line)


class ContinueLoop(object):
    """Continue to the start of a loop in an AcyclicBranchGraph."""

    def __init__(self, loop):
        self.loop = loop
        self.source = loop.source

    def __str__(self):
        return 'Continue -> {}'.format(self.loop)


class Method(object):
    def __init__(self, cobol_section, block):
        self.cobol_section = cobol_section
        self.block = block

class Block(object):
    def __init__(self):
        self.stmts = []

class If(object):
    def __init__(self, cobol_stmt, then_block, else_block, invert_condition):
        self.cobol_stmt = cobol_stmt
        self.then_block = then_block
        self.else_block = else_block
        self.invert_condition = invert_condition

class GotoLabel(object):
    def __init__(self, name, cobol_para):
        self.name = name
        self.cobol_para = cobol_para

class Goto(object):
    def __init__(self, label):
        self.label = label

class Return(object):
    pass


class Forever(object):
    """Code structure: An inifinite loop."""

    def __init__(self, cobol_para, block):
        self.cobol_para = cobol_para
        self.block = block

class While(object):
    """Code structure: a while loop with a condition."""
    def __init__(self, cobol_para, block, cobol_branch_stmt, invert_condition):
        self.cobol_para = cobol_para
        self.block = block
        self.cobol_branch_stmt = cobol_branch_stmt
        self.invert_condition = invert_condition

class Break(object):
    """Code structure: break the current loop."""
    pass


class Continue(object):
    """Code structure: continue the current loop."""
    pass


