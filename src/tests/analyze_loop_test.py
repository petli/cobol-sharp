# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import pytest

from CobolSharp.syntax import *
from CobolSharp.structure import *

from .conftest import ExpectedBlock


def test_forever_loop(cobol_block):
    """
         perform a.

       loop.
         perform b.
         go to loop.

         perform unreached.
         exit.
"""
    ExpectedBlock(
        PerformSectionStatement(None, None, 'a'),
        Forever(None, ExpectedBlock(
            PerformSectionStatement(None, None, 'b')))
    ).assert_block(cobol_block)


def test_return_in_loop(cobol_block):
    """
       loop.
         perform a.
         if x > y
             go to finish.
         perform b.
         go to loop.

       finish.
         perform c.
         exit.
"""
    ExpectedBlock(
        Forever(None, ExpectedBlock(
            PerformSectionStatement(None, None, 'a'),
            If(None, ConditionExpression(None, False),
               ExpectedBlock(
                   PerformSectionStatement(None, None, 'c'),
                   Return()),
               ExpectedBlock()),
            PerformSectionStatement(None, None, 'b')))
    ).assert_block(cobol_block)


def test_break_from_loop(cobol_block):
    """
       loop.
         perform a.

         if x > y
             go to finish.
         if x > z
             go to finish.

         perform b.
         go to loop.

       finish.
         perform c.
         exit.
"""
    ExpectedBlock(
        Forever(None, ExpectedBlock(
            PerformSectionStatement(None, None, 'a'),
            If(None, ConditionExpression(None, False),
               ExpectedBlock(Break()),
               ExpectedBlock()),
            If(None, ConditionExpression(None, False),
               ExpectedBlock(Break()),
               ExpectedBlock()),
            PerformSectionStatement(None, None, 'b'))),
        PerformSectionStatement(None, None, 'c'),
    ).assert_block(cobol_block)


def test_break_from_inner_loop(cobol_block):
    """
       outer-loop.
         perform outer-a.

       inner-loop.
         perform inner-a.

         if x > y
             go to finish-inner.
         if x > z
             go to finish-inner.

         if error = 1
             go to finish-outer.

         perform inner-b.
         go to inner-loop.

       finish-inner.
         if error = 1
             go to finish-outer.

         perform outer-b.
         go to outer-loop.

       finish-outer.
         perform c.
         exit.
"""
    finish_outer_label = GotoLabel('finish-outer', None)

    ExpectedBlock(
        Forever(None, ExpectedBlock(
            PerformSectionStatement(None, None, 'outer-a'),

            Forever(None, ExpectedBlock(
                PerformSectionStatement(None, None, 'inner-a'),
                If(None, ConditionExpression(None, False),
                   ExpectedBlock(Break()),
                   ExpectedBlock()),
                If(None, ConditionExpression(None, False),
                   ExpectedBlock(Break()),
                   ExpectedBlock()),
                If(None, ConditionExpression(None, False),
                   ExpectedBlock(Goto(finish_outer_label)),
                   ExpectedBlock()),
                PerformSectionStatement(None, None, 'inner-b'))),

            If(None, ConditionExpression(None, False),
               ExpectedBlock(Break()),
               ExpectedBlock()),
            PerformSectionStatement(None, None, 'outer-b'))),

        finish_outer_label,
        PerformSectionStatement(None, None, 'c'),
    ).assert_block(cobol_block)


def test_reduce_empty_continue_branches_in_loop(cobol_block):
    """
       loop.
         if x > y
             go to loop.
         if x > z
             go to loop.

         perform b.
         go to loop.

       unused-finish.
         exit.
"""
    ExpectedBlock(
        Forever(None, ExpectedBlock(
            If(None, ConditionExpression(None, True),
               ExpectedBlock(If(None, ConditionExpression(None, True),
                                ExpectedBlock(PerformSectionStatement(None, None, 'b')),
                                ExpectedBlock())),
               ExpectedBlock()),
        ))
    ).assert_block(cobol_block)


def test_break_while_loop(cobol_block):
    """
       loop.
         if x > y
             go to finish.
         if x > z
             go to finish.

         perform b.
         go to loop.

       finish.
         perform c.
         exit.
"""
    ExpectedBlock(
        While(None, ExpectedBlock(
                If(None, ConditionExpression(None, False),
                   ExpectedBlock(Break()),
                   ExpectedBlock()),
                PerformSectionStatement(None, None, 'b')),
              None, ConditionExpression(None, True)),
        PerformSectionStatement(None, None, 'c'),
    ).assert_block(cobol_block)


def test_continue_loop_in_nested_if(cobol_block):
    """
       loop.
         perform a.

         if x > y
             if x > z
                 go to loop.

         perform b.
         go to loop.

       unused-finish.
         exit.
"""
    ExpectedBlock(
        Forever(None, ExpectedBlock(
            PerformSectionStatement(None, None, 'a'),
            If(None, ConditionExpression(None, False),
               ExpectedBlock(If(None, ConditionExpression(None, False),
                                ExpectedBlock(Continue()),
                                ExpectedBlock())),
               ExpectedBlock()),
            PerformSectionStatement(None, None, 'b')
        ))
    ).assert_block(cobol_block)
