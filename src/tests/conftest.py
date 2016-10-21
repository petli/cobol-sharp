# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import pytest
import sys
import networkx as nx

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
def cobol_stmt_graph(request):
    """Return a StmtGraph of reachable statements of the Cobol code in the
    doc string of the unit test function.
    """
    program = parse(program_code_prefix + request.function.__doc__)
    section = program.proc_div.sections['test']
    full_graph = StmtGraph.from_section(section)
    return full_graph.reachable_subgraph()


@pytest.fixture(scope='function')
def cobol_branch_graph(cobol_stmt_graph):
    """Return a BranchJoinGraph of the Cobol code in the
    doc string of the unit test function.
    """
    return BranchJoinGraph.from_stmt_graph(cobol_stmt_graph)


@pytest.fixture(scope='function')
def cobol_dag(cobol_branch_graph):
    """Return an AcyclicBranchGraph of the Cobol code in the
    doc string of the unit test function.
    """
    return AcyclicBranchGraph.from_branch_graph(cobol_branch_graph)


@pytest.fixture(scope='function')
def cobol_block(cobol_dag):
    """Analyze the Cobol code in the doc string of the test function
    and return it as a Block object.
    """
    return cobol_dag.flatten_block()


@pytest.fixture(scope='function')
def cobol_debug_graph(cobol_stmt_graph, cobol_dag, request):
    """Add this as dependency to a unit test to debug it by printing the
    different code graphs and writing DOT files for the graphs.
    """

    print('############################################')
    print()
    cobol_stmt_graph.print_stmts()
    print()
    print('############################################')
    print()
    cobol_dag.print_nodes()
    print()
    print('############################################')

    nx.nx_agraph.write_dot(cobol_stmt_graph.graph, '{}_stmt_graph.dot'.format(request.function.__name__))
    nx.nx_agraph.write_dot(cobol_dag.graph, '{}_dag.dot'.format(request.function.__name__))


@pytest.fixture(scope='function')
def cobol_debug_block(cobol_block):
    """Add this as dependency to a unit test to debug it by printing the
    formatted pythonish code.
    """

    formatter = PythonishFormatter(TextOutputter(sys.stdout))

    print('############################################')
    print()
    formatter.format_block(cobol_block)
    print()
    print('############################################')


@pytest.fixture(scope='function')
def cobol_debug(cobol_debug_graph, cobol_debug_block):
    """Add this as dependency to a unit test to debug it by printing the
    both the code graphs and the formatted pythonish code.
    """
    pass


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
                s.then_block.assert_block(bs.then_block, spath + ':then')
                s.else_block.assert_block(bs.else_block, spath + ':else')

            elif isinstance(s, Goto):
                assert s.label.name == bs.label.name, 'Expected goto for label {}, got {} at {}'.format(
                    s.label.name, bs.label.name, spath)

            elif isinstance(s, GotoLabel):
                assert s.name == bs.name, 'Expected goto label name {}, got {} at {}'.format(
                    s.name, bs.name, spath)

            elif isinstance(s, Forever):
                s.block.assert_block(bs.block, spath)

        assert len(block.stmts) == len(self.stmts), 'Unexpected statements in {}: {}'.format(path, block.stmts)
