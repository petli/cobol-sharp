# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import pytest

from CobolSharp.syntax import *
from CobolSharp.structure import *

from .conftest import ExpectedBlock


def test_single_if(cobol_block):
    """
         if 1 > 0
             perform true-branch.
         exit.
"""
    ExpectedBlock(
        If(None, ConditionExpression(None, False),
           ExpectedBlock(PerformSectionStatement(None, None, 'true-branch')),
           ExpectedBlock()),
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
        If(None, ConditionExpression(None, False),
           ExpectedBlock(PerformSectionStatement(None, None, 'true-branch')),
           ExpectedBlock(PerformSectionStatement(None, None, 'false-branch'))),
    ).assert_block(cobol_block)


def test_remove_empty_if_branch(cobol_block):
    """
         if a > 0
             next sentence
         else
             perform false-branch.
         exit.
"""
    ExpectedBlock(
        If(None, ConditionExpression(None, True),
           ExpectedBlock(PerformSectionStatement(None, None, 'false-branch')),
           ExpectedBlock()),
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
        If(None, ConditionExpression(None, False),
           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'y')),
                            ExpectedBlock(PerformSectionStatement(None, None, 'z')))),
           ExpectedBlock(PerformSectionStatement(None, None, 'x'))),
    ).assert_block(cobol_block)


def test_structured_if(cobol_block):
    """
           if a not = 'x'
               if a = 'y'
                   perform y
               else
                   perform z
               end-if
           else
               perform x
           end-if.
           exit.
"""
    ExpectedBlock(
        If(None, ConditionExpression(None, False),
           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'y')),
                            ExpectedBlock(PerformSectionStatement(None, None, 'z')))),
           ExpectedBlock(PerformSectionStatement(None, None, 'x'))),
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

    ExpectedBlock(
        If(None, ConditionExpression(None, False),
           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-plus')),
                            ExpectedBlock(Goto(inner_false_label)))),
           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-minus')),
                            ExpectedBlock(Goto(inner_false_label))))),

        PerformSectionStatement(None, None, 'inner-true'),
        Return(),

        inner_false_label,
        PerformSectionStatement(None, None, 'inner-false'),
        Return(),
    ).assert_block(cobol_block)


def test_remove_else_when_then_returns(cobol_block):
    """
           if b > 0
               if b > 1
                   perform b-plus
                   go to finish
               else
                   go to inner-false
           else
               if b < -1
                   perform b-minus
                   go to finish
               else
                   go to inner-false.

       inner-false.
           perform inner-false
           go to finish.

       finish.
           exit program.
"""
    ExpectedBlock(
        If(None, ConditionExpression(None, False),
           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-plus'),
                                          Return()),
                            ExpectedBlock())),

           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-minus'),
                                          Return()),
                            ExpectedBlock()))),

        PerformSectionStatement(None, None, 'inner-false'),
    ).assert_block(cobol_block)


def test_remove_long_then_block_when_else_returns(cobol_block):
    """
           if b > 0
               if b > 1
                   perform b-plus
                   perform c
                   perform d
                   perform e
                   perform f
                   perform g
                   perform h
                   go to inner-true
               else
                   go to finish
           else
               if b < -1
                   perform b-minus
                   go to inner-true
               else
                   go to finish.

       inner-true.
           perform inner-true.
           go to finish.

       finish.
           exit program.
"""
    ExpectedBlock(
        If(None, ConditionExpression(None, False),
           ExpectedBlock(If(None, ConditionExpression(None, True),
                            ExpectedBlock(Return()),
                            ExpectedBlock()),
                         PerformSectionStatement(None, None, 'b-plus'),
                         PerformSectionStatement(None, None, 'c'),
                         PerformSectionStatement(None, None, 'd'),
                         PerformSectionStatement(None, None, 'e'),
                         PerformSectionStatement(None, None, 'f'),
                         PerformSectionStatement(None, None, 'g'),
                         PerformSectionStatement(None, None, 'h')),

           ExpectedBlock(If(None, ConditionExpression(None, False),
                            ExpectedBlock(PerformSectionStatement(None, None, 'b-minus')),
                            ExpectedBlock(Return())))),
        PerformSectionStatement(None, None, 'inner-true'),
    ).assert_block(cobol_block)

