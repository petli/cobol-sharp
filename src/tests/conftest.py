# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import pytest

from CobolSharp import *
from CobolSharp.structure import *
from CobolSharp.syntax import *

program_code_prefix = """
       identification division.
       program-id. test.
       environment division.
       data division.
       working-storage section.
       procedure division.
       test section.
"""


@pytest.fixture(scope='function')
def cobol_block(request):
    """Analyze the Cobol code in the doc string of the test function
    and return it as a Block object.
    """

    program = parse(program_code_prefix + request.function.__doc__)

    section = program.proc_div.sections['test']
    full_graph = StmtGraph.from_section(section)
    reachable = full_graph.reachable_subgraph()
    branch_join = BranchJoinGraph.from_stmt_graph(reachable)

    return branch_join.flatten_block()


class ExpectedBlock:
    """Helper class to get useful assertions for block equality.
    The only supported cobol statement is perform.
    """
    def __init__(self, *stmts):
        self.stmts = stmts

    def assert_block(self, block, path = None):
        for i, s in enumerate(self.stmts):
            if path:
                spath = '{}:{}'.format(path, i)
            else:
                spath = str(i)

            assert len(block.stmts) > i, 'Missing expected statement {}'.format(spath)
            bs = block.stmts[i]

            assert s.__class__ == bs.__class__, 'Expected stmt type {}, got {} at {}'.format(
                s.__class__.__name__, bs.__class__.__name__, spath)

            if isinstance(s, PerformSectionStatement):
                assert isinstance(bs, PerformSectionStatement), 'Expected perform statement at {}, got {}'.format(spath, bs)
                assert s.section_name == bs.section_name, 'Expected "perform {}", got "perform {}" at {}'.format(
                    s.section_name, bs.section_name, spath)

            elif isinstance(s, If):
                assert s.invert_condition == bs.invert_condition, 'Expected invert_condition {}, got {} at {}'.format(
                    s.invert_condition, bs.invert_condition, spath)
                s.then_block.assert_block(bs.then_block, spath)
                s.else_block.assert_block(bs.else_block, spath)

        assert len(block.stmts) == len(self.stmts), 'Unexpected statements in {}: {}'.format(path, block.stmts)
