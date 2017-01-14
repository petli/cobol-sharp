# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

class NodeBase(object):
    """Base class for all nodes in the structure graphs."""

    def __init__(self):
        self.scope = None
        self.source = None

    def _scope_id(self):
        if self.scope:
            return self.scope.source.from_line
        else:
            return None


class JumpNodeBase(NodeBase):
    """Base class for all nodes that represent any kind of jump
    (i.e. something that cannot be expressed in Jackson Structured
    Processing diagrams).
    """
    pass


class _DummySource(object):
    """This is only used to enable sorting of Entry/Exit with CobolStatements."""
    def __init__(self, from_char):
        self.from_char = from_char

class _Entry(NodeBase):
    """Singleton used as the entry node in all graphs."""

    def __str__(self):
        return 'Entry'

    source = _DummySource(-1)

Entry = _Entry()


class _Exit(JumpNodeBase):
    """Singleton used as the exit node in all graphs."""

    def __str__(self):
        return 'Exit'

    source = _DummySource(0x80000000)

Exit = _Exit()


class Branch(NodeBase):
    """A node that branches to then/else edges in structured graph."""

    def __init__(self, stmt):
        super(Branch, self).__init__()
        self.stmt = stmt
        self.condition = stmt.condition
        self.source = stmt.source

    def __str__(self):
        return 'Branch {} [{}]'.format(self.stmt, self._scope_id())


class Join(NodeBase):
    """A node where a number of edges join in a structured, but doesn't branch out again."""

    def __init__(self, stmt):
        super(Join, self).__init__()
        self.stmt = stmt
        self.source = stmt.source

    def __str__(self):
        return 'Join {} [{}]'.format(self.source.from_line, self._scope_id())


class Loop(NodeBase):
    """Start of a loop in a structured graph.

    If condition is not None, this is a conditional loop.  The
    condition=True edge goes into the loop, and condition=False to the
    statement following the loop.
    """

    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source
        self.condition = None
        self.continue_loop = None
        self.loop_exit = None

    def __str__(self):
        return 'Loop {} {} [{}]'.format(self.source.from_line, self.condition, self._scope_id())


class LoopExit(JumpNodeBase):
    """End of a loop in a structured graph"""

    def __init__(self, loop):
        super(LoopExit, self).__init__()
        self.loop = loop

    def __str__(self):
        return 'LoopExit {} [{}]'.format(self.loop.source.from_line, self._scope_id())


class ContinueLoop(JumpNodeBase):
    """Continue to the start of a loop in an structured graph."""

    def __init__(self, loop):
        super(ContinueLoop, self).__init__()
        self.loop = loop
        self.source = loop.source

    def __str__(self):
        return 'Continue -> {} [{}]'.format(self.loop, self._scope_id())


class GotoNode(JumpNodeBase):
    """Jump to a node in a structured graph."""

    def __init__(self, node):
        super(GotoNode, self).__init__()
        self.node = node
        self.source = node.source

    def __str__(self):
        return 'GotoNode -> {} [{}]'.format(self.node, self._scope_id())


class Method(object):
    def __init__(self, cobol_section, block):
        self.cobol_section = cobol_section
        self.block = block

class Block(object):
    def __init__(self):
        self.stmts = []

class If(object):
    def __init__(self, cobol_stmt, condition, then_block, else_block):
        self.cobol_stmt = cobol_stmt
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block


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

class While(NodeBase):
    """Code structure: a while loop with a condition."""
    def __init__(self, cobol_para, block, cobol_branch_stmt, condition):
        super(While, self).__init__()
        self.cobol_para = cobol_para
        self.block = block
        self.cobol_branch_stmt = cobol_branch_stmt
        self.condition = condition

class Break(object):
    """Code structure: break the current loop."""
    pass


class Continue(object):
    """Code structure: continue the current loop."""
    pass


