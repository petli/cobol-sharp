# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

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
            If(None,
               ExpectedBlock(
                   PerformSectionStatement(None, None, 'c'),
                   Return()),
               ExpectedBlock(),
               False),
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
            If(None,
               ExpectedBlock(Break()),
               ExpectedBlock(),
               False),
            If(None,
               ExpectedBlock(Break()),
               ExpectedBlock(),
               False),
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
                If(None,
                   ExpectedBlock(Break()),
                   ExpectedBlock(),
                   False),
                If(None,
                   ExpectedBlock(Break()),
                   ExpectedBlock(),
                   False),
                If(None,
                   ExpectedBlock(Goto(finish_outer_label)),
                   ExpectedBlock(),
                   False),
                PerformSectionStatement(None, None, 'inner-b'))),

            If(None,
               ExpectedBlock(Goto(finish_outer_label)),
               ExpectedBlock(),
               False),
            PerformSectionStatement(None, None, 'outer-b'))),

        finish_outer_label,
        PerformSectionStatement(None, None, 'c'),
        Return(),
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
            If(None,
               ExpectedBlock(If(None,
                                ExpectedBlock(PerformSectionStatement(None, None, 'b')),
                                ExpectedBlock(),
                                True)),
               ExpectedBlock(),
               True),
        ))
    ).assert_block(cobol_block)
