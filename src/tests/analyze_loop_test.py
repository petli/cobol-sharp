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


def test_break_from_loop(cobol_block, cobol_debug):
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
