# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

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
def cobol_structure_graph(cobol_stmt_graph):
    """Return a CobolStructureGraph of the Cobol code in the
    doc string of the unit test function.
    """
    return CobolStructureGraph.from_stmt_graph(cobol_stmt_graph)


@pytest.fixture(scope='function')
def cobol_dag(cobol_structure_graph):
    """Return an AcyclicStructureGraph of the Cobol code in the
    doc string of the unit test function.
    """
    return AcyclicStructureGraph.from_cobol_graph(cobol_structure_graph)


@pytest.fixture(scope='function')
def cobol_scope_graph(cobol_dag):
    """Return an ScopeStructuredGraph of the Cobol code in the
    doc string of the unit test function.
    """
    return ScopeStructuredGraph.from_acyclic_graph(cobol_dag, debug=True)


@pytest.fixture(scope='function')
def cobol_block(cobol_scope_graph):
    """Analyze the Cobol code in the doc string of the test function
    and return it as a Block object.
    """
    block = cobol_scope_graph.flatten_block()

    # Output the block as python to help understanding failing tests.
    # PyTest will swallow this if the test is fine.

    print('############################################')
    print()
    formatter = CodeFormatter(TextOutputter(sys.stdout, Pythonish), Pythonish)
    formatter.format_block(block)
    print()
    print('############################################')

    return block


@pytest.fixture(scope='function')
def cobol_debug(cobol_stmt_graph, cobol_scope_graph, request):
    """Add this as dependency to a unit test to debug it by printing the
    different code graphs and writing DOT files for the graphs.
    """

    print('############################################')
    print()
    cobol_stmt_graph.print_stmts()
    print()
    print('############################################')
    print()
    cobol_scope_graph.print_nodes()
    print()
    print('############################################')

    nx.nx_pydot.write_dot(cobol_stmt_graph.graph, '{}_stmt_graph.dot'.format(request.function.__name__))
    cobol_scope_graph.write_dot('{}_scope.dot'.format(request.function.__name__))


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
                assert s.condition.inverted == bs.condition.inverted, 'Expected inverted {}, got {} at {}'.format(
                    s.condition.inverted, bs.condition.inverted, spath)
                s.then_block.assert_block(bs.then_block, spath + ':then')
                s.else_block.assert_block(bs.else_block, spath + ':else')

            elif isinstance(s, Goto):
                assert s.label.name == bs.label.name, 'Expected goto for label {}, got {} at {}'.format(
                    s.label.name, bs.label.name, spath)

            elif isinstance(s, GotoLabel):
                assert s.name == bs.name, 'Expected goto label name {}, got {} at {}'.format(
                    s.name, bs.name, spath)

            elif isinstance(s, While):
                assert s.condition.inverted == bs.condition.inverted, 'Expected inverted {}, got {} at {}'.format(
                    s.condition.inverted, bs.condition.inverted, spath)
                s.block.assert_block(bs.block, spath)

            elif isinstance(s, Forever):
                s.block.assert_block(bs.block, spath)

        assert len(block.stmts) == len(self.stmts), 'Unexpected statements in {}: {}'.format(path, block.stmts)
