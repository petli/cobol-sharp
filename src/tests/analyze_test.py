# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import pytest

from CobolSharp.syntax import *
from CobolSharp.structure import *

from .conftest import ExpectedBlock


def assert_perform(stmt, expected_section):
    assert isinstance(stmt, PerformSectionStatement)
    assert stmt.section_name == expected_section


def test_empty_section(cobol_block):
    """
       exit.
"""
    ExpectedBlock(
        Return()
    ).assert_block(cobol_block)


def test_only_sequential_stmts(cobol_block):
    """
       perform first.
       perform second.
       exit.
"""
    ExpectedBlock(
        PerformSectionStatement(None, None, 'first'),
        PerformSectionStatement(None, None, 'second'),
        Return()
    ).assert_block(cobol_block)



def test_superfluous_goto(cobol_block):
    """
         perform first.
         go to do-second.
       do-second.
         perform second.
         exit.
"""
    ExpectedBlock(
        PerformSectionStatement(None, None, 'first'),
        PerformSectionStatement(None, None, 'second'),
        Return()
    ).assert_block(cobol_block)


def test_goto_skipping_stmts(cobol_block):
    """
         go to do-second.
         perform first.
       do-second.
         perform second.
         exit.
"""
    ExpectedBlock(
        PerformSectionStatement(None, None, 'second'),
        Return()
    ).assert_block(cobol_block)


def test_next_sentence_skipping_stmts(cobol_block):
    """
         next sentence
         perform first.
       do-second.
         perform second.
         exit.
"""
    ExpectedBlock(
        PerformSectionStatement(None, None, 'second'),
        Return()
    ).assert_block(cobol_block)


def test_single_if(cobol_block):
    """
         if 1 > 0
             perform true-branch.
         exit.
"""
    ExpectedBlock(
        If(None,
           ExpectedBlock(PerformSectionStatement(None, None, 'true-branch')),
           ExpectedBlock(),
           False),
        Return()
    ).assert_block(cobol_block)


def test_single_if_else(cobol_block):
    """
         if a > 0
             perform true-branch
         else
             perform false-branch.
         exit.
"""
    ExpectedBlock(
        If(None,
           ExpectedBlock(PerformSectionStatement(None, None, 'true-branch')),
           ExpectedBlock(PerformSectionStatement(None, None, 'false-branch')),
           False),
        Return()
    ).assert_block(cobol_block)


def test_reduce_goto_structured_if(cobol_block):
    """
           if a not = 'x'
               if a = 'y'
                   perform y
                   go to sub-exit
               else
                   next sentence
           else
               perform x
               go to sub-exit.

           perform z.
       sub-exit.
           exit.
"""
    ExpectedBlock(
        If(None,
           ExpectedBlock(If(None,
                            ExpectedBlock(PerformSectionStatement(None, None, 'y')),
                            ExpectedBlock(PerformSectionStatement(None, None, 'z')),
                            False)),
           ExpectedBlock(PerformSectionStatement(None, None, 'x')),
           False),
        Return()
    ).assert_block(cobol_block)


def test_reduced_crossed_if_branches(cobol_block):
    """
           if b > 0
               if b > 1
                   perform b-plus
                   go to inner-true
               else
                   go to inner-false
           else
               if b < -1
                   perform b-minus
                   go to inner-true
               else
                   go to inner-false.

       inner-true.
           perform inner-true
           go to finish.

       inner-false.
           perform inner-false
           go to finish.

       finish.
           exit program.
"""
    inner_true_label = GotoLabel('inner-true', None)
    inner_false_label = GotoLabel('inner-false', None)
    finish_label = GotoLabel('finish', None)

    ExpectedBlock(
        If(None,
           ExpectedBlock(If(None,
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-plus'),
                                          Goto(inner_true_label)),
                            ExpectedBlock(Goto(inner_false_label)),
                            False)),
           ExpectedBlock(If(None,
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-minus'),
                                          Goto(inner_true_label)),
                            ExpectedBlock(Goto(inner_false_label)),
                            False)),
           False),

        inner_true_label,
        PerformSectionStatement(None, None, 'inner-true'),
        Goto(finish_label),

        inner_false_label,
        PerformSectionStatement(None, None, 'inner-false'),
        Goto(finish_label),

        finish_label,
        Return()
    ).assert_block(cobol_block)
