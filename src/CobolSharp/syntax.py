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
        # Drop any CR in the source (could not be done when reading the source text
        #  since that would upset the character offsets reported by koopa)
        return self.text[self.from_char : self.to_char + 1].replace('\r', '')

    def __repr__(self):
        return '<Source char {0.from_char}-{0.to_char}, line {0.from_line}-{0.to_line}, column {0.from_column}-{0.to_column}>'.format(self)

class Program(object):
    def __init__(self, source, path, proc_div):
        self.source = source
        self.path = path
        self.proc_div = proc_div

    def __str__(self):
        return str(self.proc_div)


class ProcedureDivision(object):
    def __init__(self, source):
        self.source = source
        self.first_section = None
        self.sections = {}

    def sections_in_order(self):
        return sorted(self.sections.values(), key=lambda s: s.source.from_char)

    def __str__(self):
        return '\n\n'.join([str(s) for s in self.sections_in_order()])


class Section(object):
    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.comment = None
        self.first_para = None
        self.paras = {}
        self.xref_stmts = []
        self.used_sections = set()

    def get_first_stmt(self):
        if self.first_para:
            return self.first_para.get_first_stmt()

        raise None

    def paras_in_order(self):
        para = self.first_para
        while para:
            yield para
            para = para.next_para

    def __str__(self):
        return '{:5d}  {} section.\n{}'.format(
            self.source.from_line, self.name,
            '\n'.join([str(p) for p in self.paras_in_order()]))


    def __repr__(self):
        return '<Section {}>'.format(self.name)


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

        return None

    @property
    def comment(self):
        stmt = self.get_first_stmt()
        if stmt:
            return stmt.comment
        else:
            return None

    def __str__(self):
        return '{:5d}  {}.\n{}'.format(
            self.source.from_line, self.name,
            '\n'.join([str(s) for s in self.sentences]))


    def __repr__(self):
        return '<Paragraph {} in {}>'.format(self.name, repr(self.section))


class Sentence(object):
    def __init__(self, source, para):
        self.source = source
        self.para = para
        self.first_stmt = None
        self.stmts = []
        self.next_sentence = None

    def __str__(self):
        return '\n'.join([str(s) for s in self.stmts])

    def __repr__(self):
        return '<Sentence {}>'.format(repr(self.source))


class CobolStatement(object):
    def __init__(self, source, sentence):
        self.source = source
        self.sentence = sentence
        self.comment = None

    def __str__(self):
        return '{:5d}      {}'.format(self.source.from_line, self.__class__.__name__)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, repr(self.source))

    def __lt__(self, other):
        # Support sorting statements by their source code order
        if other.source is None:
            return False
        elif self.source is None:
            return True
        else:
            return self.source.from_char < other.source.from_char


class ConditionExpression(object):
    def __init__(self, source, inverted=False):
        self.source = source
        self.inverted = inverted

    def invert(self):
        """Return a new ConditionExpression object which is inverted."""
        return ConditionExpression(self.source, not self.inverted)

    def __str__(self):
        if self.inverted:
            return 'not ({})'.format(self.source)
        else:
            return str(self.source)

    def __repr__(self):
        return '<ConditionExpression invert={}: {}>'.format(self.invert, repr(self.source))


class BranchStatement(CobolStatement):
    def __init__(self, source, sentence):
        super(BranchStatement, self).__init__(source, sentence)
        self.condition = None
        self.true_stmt = None
        self.false_stmt = None

    def __str__(self):
        if self.true_stmt is not None:
            true_line = self.true_stmt.source.from_line
        else:
            true_line = 'Exit'

        if self.false_stmt is not None:
            false_line = self.false_stmt.source.from_line
        else:
            false_line = 'Exit'
            
        return '{:5d}      branch -> then {} else {}'.format(
            self.source.from_line, true_line, false_line)


class SequentialStatement(CobolStatement):
    def __init__(self, source, sentence):
        super(SequentialStatement, self).__init__(source, sentence)
        self.next_stmt = None

    def __str__(self):
        if self.next_stmt is None:
            next_line = 'Exit'
        else:
            next_line = self.next_stmt.source.from_line
            
        return '{:5d}      {} -> {}'.format(self.source.from_line, self.__class__.__name__, next_line)


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

