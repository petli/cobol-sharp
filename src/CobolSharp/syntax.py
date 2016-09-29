# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

class Source(object):
    def __init__(self, text, from_char, to_char, from_line, to_line, from_column, to_column):
        self.text = text
        self.from_char = from_char
        self.to_char = to_char
        self.from_line = from_line
        self.to_line = to_line
        self.from_column = from_column
        self.to_column = to_column

class Program(object):
    def __init__(self, source, proc_div):
        self.source = source
        self.proc_div = proc_div

class ProcedureDivision(object):
    def __init__(self, source):
        self.source = source
        self.first_section = None

class Section(object):
    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.first_para = None

class Paragraph(object):
    def __init__(self, name, source, section):
        self.name = name
        self.source = source
        self.section = section
        self.first_stmt = None
        self.next_para = None

class Sentence(object):
    def __init__(self, source, para):
        self.source = source
        self.para = para
        self.next_sentence = None

class Statement(object):
    def __init__(self, source, sentence):
        self.source = source
        self.sentence = sentence
        self.prev_stmts = []

class BranchStatement(Statement):
    def __init__(self, source, sentence):
        super(BranchStatement, this).__init__(source, sentence)
        self.expression = None
        self.true_stmt = None
        self.false_stmt = None

class GoToStatement(Statement):
    def __init__(self, source, sentence, target_name):
        super(BranchStatement, this).__init__(source, sentence)
        self.target_name = target_name
        self.target_stmt = None

class NonFlowStatement(Statement):
    def __init__(self, source, sentence):
        super(NonFlowStatement, this).__init__(source, sentence)
        self.next_stmt = None

class TerminatingStatement(Statement):
    pass

class ExitSectionStatement(TerminatingStatement):
    pass

class GobackStatement(TerminatingStatement):
    pass

class ExitProgramStatement(TerminatingStatement):
    pass

class StopRunStatement(TerminatingStatement):
    pass

