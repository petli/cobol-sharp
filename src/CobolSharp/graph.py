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


class Branch(object):
    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source

    def __str__(self):
        return 'Branch {}'.format(self.stmt)

class Join(object):
    def __init__(self, stmt):
        self.stmt = stmt
        self.source = stmt.source

    def __str__(self):
        return 'Join {}'.format(self.source.from_line)


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
    return nx.DiGraph(nx.edge_dfs(graph, Entry))


def branch_join_graph(stmt_graph):
    """Convert a graph of statements into a MultiDiGraph only containing Entry,
    Exit, Branch and Join nodes, with all non-branching statements contained
    in lists on the edge attribute 'stmts'.
    """
    branch_graph = nx.MultiDiGraph()

    branch_nodes = []
    join_nodes = []
    node_stmts = {}

    # Find all stmts that are branches or joins and wrap them
    for stmt in stmt_graph:
        if isinstance(stmt, BranchStatement):
            n = Branch(stmt)
            branch_nodes.append(n)
            node_stmts[stmt] = n

        elif stmt is Exit:
            node_stmts[Exit] = Exit

        elif stmt_graph.in_degree(stmt) > 1:
            n = Join(stmt)
            join_nodes.append(n)
            node_stmts[stmt] = n

    # Add statements from Entry node
    nbrs = stmt_graph.successors(Entry)
    assert len(nbrs) == 1
    _add_branch_edge(branch_graph, stmt_graph, node_stmts, Entry, nbrs[0])

    # Add statements from each Branch node
    for node in branch_nodes:
        _add_branch_edge(branch_graph, stmt_graph, node_stmts, node, node.stmt.true_stmt, condition=True)
        _add_branch_edge(branch_graph, stmt_graph, node_stmts, node, node.stmt.false_stmt, condition=False)

    # Add statements from all join nodes,
    for node in join_nodes:
        # Temporarily drop it to avoid detecting false self-loop
        del node_stmts[node.stmt]
        _add_branch_edge(branch_graph, stmt_graph, node_stmts, node, node.stmt)
        node_stmts[node.stmt] = node

    return branch_graph


def _add_branch_edge(branch_graph, stmt_graph, node_stmts, source_node, stmt, **attrs):
    stmts = []
    while stmt not in node_stmts:
        stmts.append(stmt)
        nbrs = stmt_graph.successors(stmt)
        assert len(nbrs) == 1
        stmt = nbrs[0]

    attrs['stmts'] = stmts
    branch_graph.add_edge(source_node, node_stmts[stmt], attr_dict=attrs)


def print_graph_stmts(graph):
    stmts = graph.nodes()
    stmts.sort(key = lambda s: s.source.from_char)
    for stmt in stmts:
        print(stmt)


def print_branch_join_graph(graph):
    nodes = graph.nodes()
    nodes.sort(key = lambda n: n.source.from_char)
    for node in nodes:
        print(node)
        for n, next_node, data in graph.out_edges_iter(node, data=True):
            if data.get('condition') == True:
                print('True:')
            elif data.get('condition') == False:
                print('False:')

            for stmt in data['stmts']:
                print(stmt)

            print('-> {}'.format(next_node))

