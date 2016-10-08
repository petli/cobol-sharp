# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import sys

import networkx as nx
from .syntax import *

class _Entry(object):
    def __str__(self):
        return 'Entry'

    source = Source('', -1, -1, -1, -1, -1, -1)

Entry = _Entry()

class _Exit(object):
    def __str__(self):
        return 'Exit'

    source = Source('', 0x80000000, 0x80000000, 0x80000000, 0x80000000, 0x80000000, 0x80000000)

Exit = _Exit()


def section_stmt_graph(section):
    """Translate a section into a directional graph of statements as nodes
    including the Entry and Exit nodes.

    Conditional edges are labeled with the attribution 'condition',
    whose value is either True or False.
    """

    g = nx.DiGraph()

    for para in section.paras.values():
        for sentence in para.sentences:
            for stmt in sentence.stmts:
                if isinstance(stmt, SequentialStatement):
                    g.add_edge(stmt, stmt.next_stmt)

                elif isinstance(stmt, BranchStatement):
                    g.add_edge(stmt, stmt.true_stmt, condition=True)
                    g.add_edge(stmt, stmt.false_stmt, condition=False)

                elif isinstance(stmt, TerminatingStatement):
                    g.add_edge(stmt, Exit)

                else:
                    raise RuntimeError('Unexpected statement type: {}'.format(stmt))

    g.add_edge(Entry, section.get_first_stmt())

    return g


def reachable_stmt_graph(graph):
    """Return the subgraph of graph only containing the reachable statements.
    """

    return nx.DiGraph(nx.dfs_edges(graph, Entry))


def print_graph_stmts(graph):
    stmts = graph.nodes()
    stmts.sort(key = lambda s: s.source.from_char)
    for stmt in stmts:
        print(stmt)


