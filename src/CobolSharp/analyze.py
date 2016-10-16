# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import networkx as nx
from .syntax import *
from .structure import *


suppressed_cobol_statements = (GoToStatement, TerminatingStatement, NextSentenceStatement)


class BlockReduction(object):
    def __init__(self, graph, start_edge=None, start_node=None, parent=None, keep_all_cobol_stmts=False):
        """Reduce a structured section of the graph into a single block.
        This is a recursive operation that reduces blocks in contained if-statements into their
        own blocks, which are then folded into this block until nothing more can be reduced.

        If start_edge is not None, it must have a single out edge
        which is the start of the block.  Otherwise start_edge is the
        starting edge which is used for the traversal.

        If parent is not None, this block will use that for detecting
        reductions and storing tail nodes.  Must not be set outside a
        recursive reduction.
        """

        self.block = Block()

        self._graph = graph

        if parent is None:
            # Map from join node to a count of the number of reduced in edges to that join in this block
            self._reduced_joins = {}

            # Map from non-reducible nodes to the sub-blocks pointing to them
            self._tail_nodes = {}

            self._keep_all_cobol_stmts = keep_all_cobol_stmts
        else:
            self._reduced_joins = parent._reduced_joins
            self._tail_nodes = parent._tail_nodes
            self._keep_all_cobol_stmts = parent._keep_all_cobol_stmts

        if start_edge is not None:
            src, node, data = start_edge
            self._add_statements(data['stmts'])
            skip_join_check = False
        else:
            assert start_node is not None
            node = start_node
            skip_join_check = True

        # Reduce a sequence of branches if possible by
        # looping as long as all join paths are accounted for
        while node is not None and node is not Exit:
            if skip_join_check:
                skip_join_check = False
            elif not self._is_reduced_join(node):
                # There are incoming edges that have not been reduced
                # in this scope, so we can't reduce further
                break

            if isinstance(node, Branch):
                node = self._reduce_if(node)
            else:
                assert node == Entry or isinstance(node, Join)
                node = self._traverse_edge(node)

        # Reached a non-reducible node
        self.dest_node = node

        if node is Exit:
            self.block.stmts.append(Return())


    def resolve_tail_nodes(self):
        # Process all tail nodes until all have been reduced.  Since
        # tail nodes might be added during this process, iterate
        # over self._tail_nodes until all nodes are in node_reduxes.

        node_reduxes = {}
        while len(node_reduxes) < len(self._tail_nodes):
            for node in self._tail_nodes.keys():
                if node not in node_reduxes:
                    redux = BlockReduction(self._graph, start_node=node, parent=self)
                    node_reduxes[node] = redux

                    if redux.dest_node is not Exit:
                        self._add_tail_node(redux.dest_node, redux.block)

                    break

        # All nodes processed, add them to this block in source code order
        node_blocks = list(self._tail_nodes.items())
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
                                    start_edge=self._get_condition_edge(edges, True),
                                    parent=self)
        else_redux = BlockReduction(self._graph,
                                    start_edge=self._get_condition_edge(edges, False),
                                    parent=self)
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


    def _get_tail_node_blocks(self, node):
        try:
            return self._tail_nodes[node]
        except KeyError:
            blocks = self._tail_nodes[node] = []
            return blocks

