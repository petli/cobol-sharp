# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

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

class Loop(object):
    def __init__(self, cobol_stmt, cobol_para):
        self.cobol_stmt = cobol_stmt
        self.cobol_para = cobol_para

class ContinueLoop(object):
    def __init__(self, loop):
        self.loop = loop

class BreakLoop(object):
    def __init__(self, loop):
        self.loop = loop

