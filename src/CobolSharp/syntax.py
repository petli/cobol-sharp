# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

class Source(object):
    def __init__(self, text, from_char, to_char, from_line, to_line, from_column, to_column):
        self.text = text
        self.from_char = from_char
        self.to_char = to_char
        self.from_line = from_line
        self.to_line = to_line
        self.from_column = from_column
        self.to_column = to_column

    def __str__(self):
        return self.text[self.from_char : self.to_char + 1]


class Program(object):
    def __init__(self, source, proc_div):
        self.source = source
        self.proc_div = proc_div

    def __str__(self):
        return str(self.proc_div)


class ProcedureDivision(object):
    def __init__(self, source):
        self.source = source
        self.first_section = None
        self.sections = {}

    def sections_in_order(self):
        sections = list(self.sections.values())
        sections.sort(key = lambda s: s.source.from_char)
        return sections

    def __str__(self):
        return '\n\n'.join([str(s) for s in self.sections_in_order()])


class Section(object):
    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.first_para = None
        self.paras = {}

    def get_first_stmt(self):
        if self.first_para:
            return self.first_para.get_first_stmt()

        raise RuntimeError("Empty section doesn't have a first statement")

    def paras_in_order(self):
        para = self.first_para
        while para:
            yield para
            para = para.next_para

    def __str__(self):
        return '{:5d}  {} section.\n{}'.format(
            self.source.from_line, self.name,
            '\n'.join([str(p) for p in self.paras_in_order()]))


class Paragraph(object):
    def __init__(self, name, source, section):
        self.name = name
        self.source = source
        self.section = section
        self.first_sentence = None
        self.sentences = []
        self.next_para = None

    def get_first_stmt(self):
        if self.first_sentence:
            return self.first_sentence.first_stmt

        if self.next_para:
            return self.next_para.get_first_stmt()

        raise RuntimeError("Last paragraph in section is empty, cannot find first statement")

    def __str__(self):
        return '{:5d}  {}.\n{}'.format(
            self.source.from_line, self.name,
            '\n'.join([str(s) for s in self.sentences]))


class Sentence(object):
    def __init__(self, source, para):
        self.source = source
        self.para = para
        self.first_stmt = None
        self.stmts = []
        self.next_sentence = None

    def __str__(self):
        return '\n'.join([str(s) for s in self.stmts])


class CobolStatement(object):
    def __init__(self, source, sentence):
        self.source = source
        self.sentence = sentence

    def __str__(self):
        return '{:5d}      {}'.format(self.source.from_line, self.__class__.__name__)


class BranchStatement(CobolStatement):
    def __init__(self, source, sentence):
        super(BranchStatement, self).__init__(source, sentence)
        self.condition = None
        self.true_stmt = None
        self.false_stmt = None

    def __str__(self):
        return '{:5d}      branch -> then {} else {}'.format(
            self.source.from_line, self.true_stmt.source.from_line, self.false_stmt.source.from_line)


class SequentialStatement(CobolStatement):
    def __init__(self, source, sentence):
        super(SequentialStatement, self).__init__(source, sentence)
        self.next_stmt = None

    def __str__(self):
        return '{:5d}      {} -> {}'.format(self.source.from_line, self.__class__.__name__, self.next_stmt.source.from_line)


class GoToStatement(SequentialStatement):
    def __init__(self, source, sentence, para_name):
        super(GoToStatement, self).__init__(source, sentence)
        self.para_name = para_name


class NextSentenceStatement(SequentialStatement):
    pass

class MoveStatement(SequentialStatement):
    pass

class PerformSectionStatement(SequentialStatement):
    def __init__(self, source, sentence, section_name):
        super(PerformSectionStatement, self).__init__(source, sentence)
        self.section_name = section_name
        self.section = None

class UnparsedStatement(SequentialStatement):
    pass


class TerminatingStatement(CobolStatement):
    pass

class ExitSectionStatement(TerminatingStatement):
    pass

class GobackStatement(TerminatingStatement):
    pass

class ExitProgramStatement(TerminatingStatement):
    pass

class StopRunStatement(TerminatingStatement):
    pass

