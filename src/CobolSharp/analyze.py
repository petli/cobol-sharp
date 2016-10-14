# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import networkx as nx
from .graph import *
from .syntax import *
from .structure import *


suppressed_cobol_statements = (GoToStatement, TerminatingStatement, NextSentenceStatement)

def branch_join_graph_to_block(graph, keep_all_cobol_stmts=False):
    # TODO: resolve loops to translate into DAG

    edges = graph.out_edges(Entry, data=True)
    assert len(edges) == 1

    redux = BlockReduction(graph, edges[0], keep_all_cobol_stmts=keep_all_cobol_stmts)
    redux.resolve_tail_nodes()

    return redux.block



class BlockReduction(object):
    def __init__(self, graph, start_edge, keep_all_cobol_stmts, reduced_joins = None, traverse_first_edge=False, ):
        self._graph = graph
        self._reduced_joins = reduced_joins if reduced_joins is not None else {}
        self._keep_all_cobol_stmts = keep_all_cobol_stmts
        self.block = Block()

        # Map from non-reducible nodes to the sub-blocks pointing to them
        self.tail_nodes = {}

        src, dest, data = start_edge
        self._add_statements(data['stmts'])

        skip_join_check = traverse_first_edge

        # Reduce a sequence of branches if possible by
        # looping as long as all join paths are accounted for
        while dest is not None and dest is not Exit:
            if skip_join_check:
                skip_join_check = False
            elif not self._is_reduced_join(dest):
                # There are incoming edges that have not been reduced
                # in this scope, so we can't reduce further
                break

            if isinstance(dest, Branch):
                dest = self._reduce_if(dest)

            else:
                assert isinstance(dest, Join)
                dest = self._traverse_edge(dest)

        # Reached a non-reducible node
        self.dest_node = dest

        if dest is Exit:
            self.block.stmts.append(Return())


    def resolve_tail_nodes(self):
        # Stack of tail nodes left to process
        nodes = list(self.tail_nodes.keys())
        node_reduxes = {}
        while nodes:
            node = nodes.pop()

            # Fake an input edge to this node so it can be reduced
            edge = (None, node, {'stmts': []})
            redux = BlockReduction(self._graph, edge,
                                   keep_all_cobol_stmts=self._keep_all_cobol_stmts,
                                   traverse_first_edge=True)
            node_reduxes[node] = redux

            if redux.dest_node is not Exit:
                self._add_tail_node(redux.dest_node, redux.block)
                nodes.append(redux.dest_node)

            self._add_redux_tail_nodes(redux)
            nodes.extend(redux.tail_nodes.keys())

        # All nodes processed, add them to this block in source code order
        node_blocks = list(self.tail_nodes.items())
        node_blocks.sort(key = lambda n: n[0].source.from_char)

        node_labels = {}
        for node, blocks in node_blocks:
            if node is Exit:
                label = GotoLabel('__exit', None)
            else:
                para = node.stmt.sentence.para
                assert node.stmt == para.get_first_stmt()
                label = GotoLabel(para.name or '__start', para)

            # Wire source blocks to point to this label
            for block in blocks:
                block.stmts.append(Goto(label))

            node_labels[node] = label

        for node, blocks in node_blocks:
            redux = node_reduxes[node]
            self.block.stmts.append(node_labels[node])
            self.block.stmts.extend(redux.block.stmts)

    def _add_statements(self, stmts):
        if not self._keep_all_cobol_stmts:
            stmts = [s for s in stmts if not isinstance(s, suppressed_cobol_statements)]

        self.block.stmts.extend(stmts)


    def _is_reduced_join(self, node):
        num_joins = self._reduced_joins.get(node, 0)
        return self._graph.in_degree(node) - num_joins <= 1


    def _reduce_if(self, branch):
        edges = self._graph.out_edges(branch, data=True)
        assert len(edges) == 2

        then_redux = BlockReduction(self._graph,
                                    self._get_condition_edge(edges, True),
                                    keep_all_cobol_stmts=self._keep_all_cobol_stmts,
                                    reduced_joins=self._reduced_joins)
        else_redux = BlockReduction(self._graph,
                                    self._get_condition_edge(edges, False),
                                    keep_all_cobol_stmts=self._keep_all_cobol_stmts,
                                    reduced_joins=self._reduced_joins)
        invert_condition = False
        tail_stmts = []

        # In a structured if statement the subblocks both lead to the same
        # node, so the block continues there
        if then_redux.dest_node == else_redux.dest_node:
            dest = then_redux.dest_node

            # Account this join in the scope
            n = self._reduced_joins.get(dest, 0)
            self._reduced_joins[dest] = n + 1

        # Different paths
        else:
            # If the else block terminates, flip condition so we can avoid the
            # else branch altogether
            if else_redux.dest_node is Exit:
                then_redux, else_redux = else_redux, then_redux
                invert_condition = True

            # If the then block terminates, merge the else block into this one
            # to reduce the if block
            if then_redux.dest_node is Exit:
                dest = else_redux.dest_node
                tail_stmts = else_redux.block.stmts
                else_redux.block = Block()

            # Paths diverge and doesn't exit, cannot do anything about this
            else:
                self._add_tail_node(then_redux.dest_node, then_redux.block)
                self._add_tail_node(else_redux.dest_node, else_redux.block)
                dest = None

        self.block.stmts.append(If(branch.stmt, then_redux.block, else_redux.block, invert_condition))
        self.block.stmts.extend(tail_stmts)
        self._add_redux_tail_nodes(then_redux)
        self._add_redux_tail_nodes(else_redux)

        return dest


    def _get_condition_edge(self, edges, value):
        """Return the edge where attribute 'condition' has the desired value."""
        for edge in edges:
            data = edge[2]
            if data['condition'] == value:
                return edge

        assert False, 'None of the edges have the expected condition'


    def _traverse_edge(self, node):
        edges = self._graph.out_edges(node, data=True)
        assert len(edges) == 1
        n, next, data = edges[0]
        self._add_statements(data['stmts'])
        return next

    def _add_tail_node(self, node, block):
        blocks = self._get_tail_node_blocks(node)
        blocks.append(block)

    def _add_redux_tail_nodes(self, redux):
        for node, redux_blocks in redux.tail_nodes.items():
            blocks = self._get_tail_node_blocks(node)
            blocks.extend(redux_blocks)

    def _get_tail_node_blocks(self, node):
        try:
            return self.tail_nodes[node]
        except KeyError:
            blocks = self.tail_nodes[node] = []
            return blocks

