# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import networkx as nx
from .syntax import *
from .structure import *
from .analyze import BlockReduction

class StmtGraph(object):
    """Holds a directional graph of statements as nodes including the
    Entry and Exit nodes.

    Conditional edges are labeled with the attribution 'condition',
    whose value is either True or False.

    If the graph itself needs to be referenced it is held in the
    object property "graph".
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    @classmethod
    def from_section(cls, section):
        """Translate a Cobol Section into a statement graph.
        """
        stmt_graph = cls()
        g = stmt_graph.graph

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

        return stmt_graph


    def reachable_subgraph(self):
        """Return a new StmtGraph that only contains the nodes reachable from
        Entry.
        """
        sub_graph = StmtGraph()
        sub_graph.graph.add_edges_from(nx.edge_dfs(self.graph, Entry))
        return sub_graph


    def print_stmts(self):
        stmts = self.graph.nodes()
        stmts.sort(key = lambda s: s.source.from_char)
        for stmt in stmts:
            print(stmt)


class BranchJoinGraph(object):
    """A MultiDiGraph representing the structure of a Cobol program.

    Instead of statements, the graph nodes are one of:

    ## Entry singleton:
    Start of execution. No in edges, one out edge.

    ## Exit singleton:
    End of execution.  At least one in edge, no out edges.

    ## Branch instances:
    At least one in edge, two out edges.  The out edges are identified by the attributes
    condition=True and condition=False, respectively.

    ## Join instances:
    At least two in edges, one out edge.

    The edges between the nodes holds the sequential cobol statements in the
    edge attribute 'stmts'.  This may be an empty list, but it is always present.
    """

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    @classmethod
    def from_stmt_graph(cls, stmt_graph):
        branch_join_graph = cls()

        branch_nodes = []
        join_nodes = []
        node_stmts = {}

        # Find all stmts that are branches or joins and wrap them
        for stmt in stmt_graph.graph:
            if isinstance(stmt, BranchStatement):
                n = Branch(stmt)
                branch_nodes.append(n)
                node_stmts[stmt] = n

            elif stmt is Exit:
                node_stmts[Exit] = Exit

            elif stmt_graph.graph.in_degree(stmt) > 1:
                n = Join(stmt)
                join_nodes.append(n)
                node_stmts[stmt] = n

        # Add statements from Entry node
        nbrs = stmt_graph.graph.successors(Entry)
        assert len(nbrs) == 1
        branch_join_graph._add_branch_edge(stmt_graph, node_stmts, Entry, nbrs[0])

        # Add statements from each Branch node
        for node in branch_nodes:
            branch_join_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt.true_stmt, condition=True)
            branch_join_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt.false_stmt, condition=False)

        # Add statements from all join nodes,
        for node in join_nodes:
            # Temporarily drop it to avoid detecting false self-loop
            del node_stmts[node.stmt]
            branch_join_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt)
            node_stmts[node.stmt] = node

        return branch_join_graph


    def _add_branch_edge(self, stmt_graph, node_stmts, source_node, stmt, **attrs):
        stmts = []
        while stmt not in node_stmts:
            stmts.append(stmt)
            nbrs = stmt_graph.graph.successors(stmt)
            assert len(nbrs) == 1
            stmt = nbrs[0]

        attrs['stmts'] = stmts
        self.graph.add_edge(source_node, node_stmts[stmt], attr_dict=attrs)


    def print_nodes(self):
        nodes = self.graph.nodes()
        nodes.sort(key = lambda n: n.source.from_char)
        for node in nodes:
            print(node)
            for n, next_node, data in self.graph.out_edges_iter(node, data=True):
                if data.get('condition') == True:
                    print('True:')
                elif data.get('condition') == False:
                    print('False:')

                for stmt in data['stmts']:
                    print(stmt)

                print('-> {}'.format(next_node))


    def flatten_block(self, keep_all_cobol_stmts=False):
        """Translate the graph structure to a Block of CobolStatement or
        structure elements and return it.
        """
        # TODO: should be done on a DAG instead

        redux = BlockReduction(self.graph, start_node=Entry, keep_all_cobol_stmts=keep_all_cobol_stmts)
        redux.resolve_tail_nodes()
        return redux.block
