# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

"""Parse Cobol code using koopa.
"""


# java -cp ~/src/koopa-r356.jar -Dkoopa.xml.include_positioning=true koopa.app.cli.ToXml testsyntax.cbl /tmp/testsyntax.xml

import subprocess
import os
from pkg_resources import resource_filename
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET

from .syntax import *

class ParserError(Exception): pass

def parse(source, java_binary = 'java'):
    """Parse Cobol code in 'source', which must be a text file-like object
    with a read() method or a string.

    Returns a Program object.
    """

    if hasattr(source, 'read'):
        code = source.read()
    elif isinstance(source, str):
        code = source
    else:
        raise TypeError('source must be a file-like object or a string')

    return ProgramParser(code, java_binary).program


class ProgramParser(object):
    KOOPA_JAR = 'data/koopa-r356.jar'

    def __init__(self, code, java_binary):
        self._code = code

        self._perform_stmts = []

        self._run_koopa(java_binary)
        self._parse()

    def _run_koopa(self, java_binary):
        source_file = None
        result_file = None

        try:
            source_file = NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.cbl', delete=False)
            source_file.write(self._code)
            source_file.close()

            # Just grab a temp file name for the results
            result_file = NamedTemporaryFile(mode='wb', suffix='.xml', delete=False)
            result_file.close()

            jar = resource_filename('CobolSharp', self.KOOPA_JAR)

            cmd = (java_binary, '-cp', jar, '-Dkoopa.xml.include_positioning=true',
                   'koopa.app.cli.ToXml', source_file.name, result_file.name)

            process = subprocess.Popen(cmd,
                                       stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       universal_newlines=True)

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise ParserError(stdout)

            self._tree = ET.parse(result_file.name)

        finally:
            pass
            if source_file:
                os.remove(source_file.name)
            if result_file:
                os.remove(result_file.name)


    def _parse(self):
        unit_el = self._tree.find('compilationGroup')
        proc_div_el = unit_el.find('.//procedureDivision')

        proc_div = ProcedureDivision(self._source(proc_div_el))

        self.program = Program(self._source(unit_el), proc_div)

        section_els = proc_div_el.findall('section')

        # Construct a default main section if there's loose paragraphs
        # or sentences at the start

        main_sentence_els = proc_div_el.findall('sentence')
        main_para_els = proc_div_el.findall('paragraph')

        if main_sentence_els:
            main_para_els.insert(0, self._virtual_element('paragraph', main_sentence_els))

        if main_para_els:
            section_els.insert(0, self._virtual_element('tag', main_para_els))

        for el in section_els:
            section = self._parse_section(el)
            proc_div.sections[section.name] = section

        proc_div.first_section = section


    def _parse_section(self, section_el):
        # Process the paragraphs, sentences and statements backward
        # to be able to easily link up statements

        name_el = section_el.find('./sectionName/name/cobolWord/t')
        if name_el is not None:
            name = name_el.text.lower()
        else:
            name = None

        section = Section(name, self._source(section_el))

        self._goto_stmts = []

        para_els = section_el.findall('paragraph')
        para_els.reverse()

        para = None
        for el in para_els:
            para = self._parse_para(el, section, para)
            section.paras[para.name] = para

        # If there are initial sentences before any paragraph, parse
        # them as a dummy paragraph
        sentence_els = section_el.findall('sentence')
        if sentence_els:
            para = self._parse_para(self._virtual_element('paragraph', sentence_els), section, para)
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

        stmt = next_stmt
        for el in stmt_els:
            stmt = self._parse_stmt(el, sentence, stmt)
            sentence.stmts.append(stmt)

        return stmt


    def _parse_stmt(self, stmt_el, sentence, next_stmt):
        stmt_type_el = stmt_el[0]

        try:
            parse_func = getattr(self, '_parse_stmt_' + stmt_type_el.tag)
        except AttributeError:
            raise ParserError('line {}: unsupported statement type: {}'.format(
                stmt_el.get('from-line'), stmt_type_el.tag))

        stmt = parse_func(stmt_type_el, sentence, next_stmt)
        return stmt


    def _parse_stmt_exitStatement(self, exit_el, sentence, next_stmt):
        endpoint_el = exit_el.find('./endpoint/t')

        if endpoint_el is None:
            stmt = ExitSectionStatement(self._source(exit_el), sentence)

        elif endpoint_el.text.lower() == 'program':
            stmt = ExitProgramStatement(self._source(exit_el), sentence)

        else:
            raise ParserError('line {}: unsupported exit statement'.format(
                stmt_el.get('from-line')))

        return stmt


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
        stmt.condition = self._source(condition_el)

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

        proc_name = proc_name_el.text

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

