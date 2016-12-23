# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import pytest

from CobolSharp.syntax import *
from CobolSharp.structure import *

from .conftest import ExpectedBlock


def test_empty_section(cobol_block):
    """
       exit.
"""
    ExpectedBlock(
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
    ).assert_block(cobol_block)


def test_unparsed_stmt(cobol_block):
    """
       initialize a.
       exit.
"""
    ExpectedBlock(
        UnparsedStatement(None, None),
    ).assert_block(cobol_block)

