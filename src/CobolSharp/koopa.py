# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

"""Parse Cobol code using koopa.
"""


# java -cp ~/src/koopa-r356.jar -Dkoopa.xml.include_positioning=true koopa.app.cli.ToXml testsyntax.cbl /tmp/testsyntax.xml

import subprocess
import os
import sys
from pkg_resources import resource_filename
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

from .syntax import *

KOOPA_JAR = 'data/koopa-r356.jar'

class ParserError(Exception): pass

def parse(source, java_binary='java', tabsize=4):
    """Parse Cobol code in 'source', which must be a text file-like object
    with a read() method or a string.

    Returns a Program object.
    """
    return ProgramParser(source, java_binary, tabsize).program


def run_koopa(source, output_path, java_binary='java', tabsize=4):
    """Run Koopa to parse 'source', either a text file-like object with a
    read() method or a string, into an XML document saved to
    output_path.

    Returns the Cobol source code as a string, with expanded tabs.
    """

    if hasattr(source, 'read'):
        code = source.read()
        code_path = source.name
    elif isinstance(source, str):
        code = source
        code_path = '<string>'
    else:
        raise TypeError('source must be a file-like object or a string')

    source_file = None
    try:
        # Regardless of source encoding, save as a single-byte encoding since Cobol parsing
        # should only need ascii chars.  Saving as UTF-8 or similar means that the character
        # ranges reported by koopa will be offset from the data in self._code, breaking extracting
        # symbols etc.

        # But save as iso-8859-1, to keep more national chars in comments.
        # TODO: use input file encoding if it is single-byte.

        # Since NamedTemporaryFile doesn't support specifying encoding error handling,
        # encode the bytes ourselves to replace non-ascii with ? to preserve char counts.

        source_file = NamedTemporaryFile(mode='wb', suffix='.cbl', delete=False)
        source_file.write(code.encode('iso-8859-1', errors='replace'))
        source_file.close()

        jar = resource_filename('CobolSharp', KOOPA_JAR)

        # TODO: add command arg to control heap size
        cmd = (java_binary, '-cp', jar, '-Xms500m', '-Dkoopa.xml.include_positioning=true',
               'koopa.app.cli.ToXml', source_file.name, output_path)

        process = subprocess.Popen(cmd,
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True)

        stdout, stderr = process.communicate()

        # Doesn't seem to return an error exit code on parse errors...
        if process.returncode != 0 or 'Error:' in stdout:
            msg = stdout.replace(source_file.name, code_path)
            msg = msg.replace(os.path.basename(source_file.name), code_path)
            raise ParserError(msg)

        return code
    
    finally:
        if source_file:
            os.remove(source_file.name)


class ProgramParser(object):
    def __init__(self, source, java_binary, tabsize):
        self._perform_stmts = []

        if hasattr(source, 'name'):
            self._source_path = source.name
        else:
            self._source_path = '<string>'

        # Just grab a temp file name for the results
        result_file = NamedTemporaryFile(mode='wb', suffix='.xml', delete=False)
        result_file.close()

        try:
            self._code = run_koopa(source, result_file.name, java_binary=java_binary, tabsize=tabsize)
            parser = ET.XMLParser(target=CommentTreeBuilder())
            self._tree = ET.parse(result_file.name, parser=parser)
        finally:
            if result_file:
                os.remove(result_file.name)

        self._parse()


    def _warn(self, element_or_source, msg):
        if isinstance(element_or_source, Source):
            line = element_or_source.from_line
        else:
            line = element_or_source.get('from-line')

        sys.stderr.write('{}: line {}: {}\n'.format(self._source_path, line, msg))


    def _parse(self):
        unit_el = self._tree.find('compilationGroup')
        proc_div_el = unit_el.find('.//procedureDivision')

        proc_div = ProcedureDivision(self._source(proc_div_el))

        self.program = Program(self._source(unit_el), self._source_path, proc_div)

        section_els = proc_div_el.findall('section')

        # Construct a default main section if there's loose paragraphs
        # or sentences at the start

        main_sentence_els = proc_div_el.findall('sentence')
        main_para_els = proc_div_el.findall('paragraph')

        if main_sentence_els:
            main_para_els.insert(0, self._virtual_element('paragraph', main_sentence_els))

        if main_para_els:
            section_els.insert(0, self._virtual_element('tag', main_para_els))

        section = None
        for el in section_els:
            section = self._parse_section(el)
            if section.name in proc_div.sections:
                self._warn(el, 'duplicate section: {}'.format(section.name))
                section.name += '__dup{}'.format(id(section))

            proc_div.sections[section.name] = section

            if proc_div.first_section is None:
                proc_div.first_section = section


        # Resolve section references
        for stmt in self._perform_stmts:
            ref_section = proc_div.sections.get(stmt.section_name)
            if ref_section:
                stmt.section = ref_section
                stmt.sentence.para.section.used_sections.add(ref_section)
                ref_section.xref_stmts.append(stmt)
            else:
                self._warn(stmt.source, 'reference to undefined section: {}'.format(stmt.section_name))


    def _parse_section(self, section_el):
        # Process the paragraphs, sentences and statements backward
        # to be able to easily link up statements

        name_el = section_el.find('./sectionName/name/cobolWord/t')
        if name_el is not None:
            name = name_el.text.lower()
        else:
            name = '__main'

        section = Section(name, self._source(section_el))
        comment_el = section_el.find('_comment')
        if comment_el is not None:
            section.comment = comment_el.text.rstrip()

        self._goto_stmts = []

        para_els = section_el.findall('paragraph')
        para_els.reverse()

        # If there are initial sentences before any paragraph, parse
        # them as a dummy paragraph
        sentence_els = section_el.findall('sentence')
        if sentence_els:
            para_els.append(self._virtual_element('paragraph', sentence_els))

        para = None
        for el in para_els:
            para = self._parse_para(el, section, para)
            if para.name in section.paras:
                self._warn(el, 'duplicate paragraph: {}'.format(para.name))
                para.name += '__dup{}'.format(id(para))

            section.paras[para.name] = para

        section.first_para = para

        # Resolve gotos
        for stmt in self._goto_stmts:
            try:
                target_para = section.paras[stmt.para_name]
            except KeyError:
                raise ParserError('line {}: undefined go to target paragraph: {}'.format(
                    stmt.source.from_line, stmt.para_name))

            stmt.next_stmt = target_para.get_first_stmt()

        self._goto_stmts = []

        return section


    def _parse_para(self, para_el, section, next_para):
        name_el = para_el.find('./paragraphName/name/cobolWord/t')
        if name_el is not None:
            name = name_el.text.lower()
        else:
            name = None

        para = Paragraph(name, self._source(para_el), section)
        para.next_para = next_para

        sentence_els = para_el.findall('sentence')
        sentence_els.reverse()

        sentence = next_para.first_sentence if next_para else None
        for el in sentence_els:
            sentence = self._parse_sentence(el, para, sentence)
            para.sentences.append(sentence)

        para.first_sentence = sentence
        para.sentences.reverse()
        return para


    def _parse_sentence(self, sentence_el, para, next_sentence):
        sentence = Sentence(self._source(sentence_el), para)
        sentence.next_sentence = next_sentence

        stmt_els = sentence_el.findall('statement')

        next_stmt = next_sentence.first_stmt if next_sentence else None
        sentence.first_stmt = self._parse_stmts(stmt_els, sentence, next_stmt)
        sentence.stmts.reverse()
        return sentence


    def _parse_stmts(self, stmt_els, sentence, next_stmt):
        stmt_els.reverse()

        stmt = None
        for el in stmt_els:
            stmt = self._parse_stmt(el, sentence, next_stmt)
            if stmt is not None:
                sentence.stmts.append(stmt)
                next_stmt = stmt

        return stmt


    def _parse_stmt(self, stmt_el, sentence, next_stmt):
        comment_el = stmt_el.find('_comment')
        if comment_el is not None:
            stmt_type_el = stmt_el[1]
        else:
            stmt_type_el = stmt_el[0]

        try:
            parse_func = getattr(self, '_parse_stmt_' + stmt_type_el.tag)
        except AttributeError:
            parse_func = self._unparsed_stmt

        stmt = parse_func(stmt_type_el, sentence, next_stmt)
        if stmt and comment_el is not None:
            stmt.comment = comment_el.text.rstrip()

        return stmt

    def _unparsed_stmt(self, stmt_el, sentence, next_stmt):
        stmt = UnparsedStatement(self._source(stmt_el), sentence)
        stmt.next_stmt = next_stmt
        return stmt


    def _parse_stmt_exitStatement(self, exit_el, sentence, next_stmt):
        source = self._source(exit_el)
        endpoint_el = exit_el.find('./endpoint/t')

        if endpoint_el is None:
            # A no-op Exit statement
            if next_stmt is not None:
                self._warn(exit_el, 'EXIT statement (which is a no-op) is not the last one in the section.')
            stmt = None

        elif endpoint_el is 'section':
            stmt = ExitSectionStatement(source, sentence)

        elif endpoint_el.text.lower() == 'program':
            stmt = ExitProgramStatement(source, sentence)

        else:
            raise ParserError('line {}: unsupported exit statement'.format(
                stmt_el.get('from-line')))

        return stmt


    def _parse_stmt_gobackStatement(self, el, sentence, next_stmt):
        return GobackStatement(self._source(el), sentence)


    def _parse_stmt_goToStatement(self, goto_el, sentence, next_stmt):
        proc_name_el = goto_el.find('./procedureName/name/cobolWord/t')
        proc_name = proc_name_el.text.lower()

        stmt = GoToStatement(self._source(goto_el), sentence, proc_name)
        self._goto_stmts.append(stmt)

        return stmt


    def _parse_stmt_ifStatement(self, if_el, sentence, next_stmt):
        stmt = BranchStatement(self._source(if_el), sentence)

        # For now, just grab the source instead of the whole expression
        condition_el = if_el.find('condition')
        stmt.condition = ConditionExpression(self._source(condition_el))

        else_el = if_el.find('elseBranch')
        if else_el is not None:
            stmt.false_stmt = self._parse_stmts(
                else_el.findall('./nestedStatements/statement'), sentence, next_stmt)
        else:
            stmt.false_stmt = next_stmt

        then_el = if_el.find('thenBranch')
        stmt.true_stmt = self._parse_stmts(
            then_el.findall('./nestedStatements/statement'), sentence, next_stmt)

        return stmt


    def _parse_stmt_moveStatement(self, move_el, sentence, next_stmt):
        stmt = MoveStatement(self._source(move_el), sentence)
        stmt.next_stmt = next_stmt
        return stmt


    def _parse_stmt_nextSentenceStatement(self, move_el, sentence, next_stmt):
        stmt = NextSentenceStatement(self._source(move_el), sentence)

        if sentence.next_sentence:
            stmt.next_stmt = sentence.next_sentence.first_stmt

        return stmt


    def _parse_stmt_performStatement(self, perform_el, sentence, next_stmt):
        proc_name_el = perform_el.find('./procedureName/name/cobolWord/t')

        if proc_name_el is None:
            raise ParserError('line {}: unsupported perform statement'.format(
                perform_el.get('from-line')))

        proc_name = proc_name_el.text.lower()

        stmt = PerformSectionStatement(self._source(perform_el), sentence, proc_name)
        stmt.next_stmt = next_stmt
        self._perform_stmts.append(stmt)

        return stmt


    def _virtual_element(self, tag, children):
        first = children[0]
        last = children[-1]
        el = ET.Element(tag, {
            'from': first.get('from'),
            'to': last.get('to'),
            'from-line': first.get('from-line'),
            'to-line': last.get('to-line'),
            'from-column': first.get('from-column'),
            'to-column': last.get('to-column') })
        el.extend(children)
        return el


    def _source(self, element):
        return Source(self._code,
                      int(element.get('from')) - 1,
                      int(element.get('to')) - 1,
                      int(element.get('from-line')),
                      int(element.get('to-line')),
                      int(element.get('from-column')) - 1,
                      int(element.get('to-column')) - 1)


class CommentTreeBuilder(ET.TreeBuilder):
    """Collect comments and insert them as a <_comment>text...</_comment>
    tag inside the following section or statement element.
    """

    def __init__(self):
        super().__init__()
        self._comments = None

    def comment(self, data):
        if self._comments is not None:
            self._comments.append(data)

    def start(self, tag, attrs):
        super().start(tag, attrs)

        # Start collecting comments now
        if tag == 'procedureDivision':
            self._comments = []

        if (tag == 'section' or tag == 'statement'):
            if self._comments:            
                super().start('_comment', {})
                for data in self._comments:
                    self.data(data)
                    self.data('\n')
                super().end('_comment')
                self._comments = []
