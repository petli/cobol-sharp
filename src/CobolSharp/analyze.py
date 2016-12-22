# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>

import networkx as nx
from .syntax import *
from .structure import *


suppressed_cobol_statements = (GoToStatement, TerminatingStatement, NextSentenceStatement)

def suppress_statements(stmts):
    return [s for s in stmts if not isinstance(s, suppressed_cobol_statements)]


class ReductionScope(object):
    def __init__(self, graph, keep_all_cobol_stmts=False):
        self._graph = graph
        self.keep_all_cobol_stmts = keep_all_cobol_stmts

        # Map from join node to a count of the number of reduced in edges to that join in this scope
        self._reduced_joins = {}

        # Map unreduced destination nodes to the reduxes going to them
        self._tail_reduxes = {}


    def add_tail_redux(self, redux, possible_loop_break=True):
        if redux.dest_node is None:
            return

        reduxes = self._get_tail_reduxes(self._tail_reduxes, redux.dest_node)
        reduxes.append(redux)


    def _get_tail_reduxes(self, node_dict, node):
        try:
            return node_dict[node]
        except KeyError:
            reduxes = node_dict[node] = []
            return reduxes


    def reduce_join(self, node):
        n = self._reduced_joins.get(node, 0)
        self._reduced_joins[node] = n + 1


    def unreduced_join_edges(self, node):
        """Return the number of in edges to node that hasn't been
        reduced yet.
        """
        num_joins = self._reduced_joins.get(node, 0)
        return self._graph.in_degree(node) - num_joins


    def is_reduced_join(self, node):
        """Return True if this node only has at most one unreduced in edge.
        """
        return self.unreduced_join_edges(node) <= 1


    def is_node_main_scope(self, node):
        """Return True if this is the main scope for this node, i.e. there is
        no child scope that the node also belongs to.
        """
        # Root scope accepts all nodes
        return True


    def is_node_scope(self, node):
        """Return True if the node belongs to this scope or a child scope.
        """
        # Root scope accepts all nodes
        return True


class LoopReductionScope(ReductionScope):
    def __init__(self, parent, loop):
        super(LoopReductionScope, self).__init__(parent._graph, parent.keep_all_cobol_stmts)
        self._parent = parent
        self._loop = loop

        # Like _tail_reduxes, but for nodes pointing into parent scope
        self._break_reduxes = {}


    def add_tail_redux(self, redux, possible_loop_break=True):
        if redux.dest_node is None:
            return

        # Does it belong to this loop?
        if self.is_node_main_scope(redux.dest_node):
            super(LoopReductionScope, self).add_tail_redux(redux)
            return

        # Does it break into the parent loop?
        if possible_loop_break and self._parent.is_node_main_scope(redux.dest_node):
            # Can only be a break if all edges to the dest_node belongs in this loop scope
            if False not in (self.is_node_main_scope(n)
                             for n in self._graph.predecessors_iter(redux.dest_node)):
                reduxes = self._get_tail_reduxes(self._break_reduxes, redux.dest_node)
                reduxes.append(redux)
                return

        # Otherwise recurse up to add it to the scope it belongs to
        self._parent.add_tail_redux(redux, possible_loop_break=False)


    def is_node_main_scope(self, node):
        return node is not None and self._loop is self._graph.node[node].get('loop')


    def is_node_scope(self, node):
        return node is not None and self._loop in self._graph.node[node].get('loops', ())


    def pop_continue_node(self):
        nodes = [n for n in self._tail_reduxes
                 if isinstance(n, ContinueLoop) and n.loop == self._loop]

        if not nodes:
            return None

        assert len(nodes) == 1
        return self._tail_reduxes.pop(nodes[0])


class ReductionBase(object):
    def __init__(self, graph, scope):
        self._graph = graph
        self._scope = scope

        self.block = Block()
        self.dest_node = None


    def _out_edge(self, node):
        """Follow a single edge from node, returning a tuple:
        (node, dest_node, edge_data)
        """
        edges = self._graph.out_edges(node, data=True)
        assert len(edges) == 1
        return edges[0]


    def _out_condition_edges(self, branch_node):
        """Follow the condition edges leading out from a branch node, returning a tuple
        (then_edge, else_edge) where each edge is a tuple (node, dest_node, edge_data).
        """

        then_edge = else_edge = None

        for edge in self._graph.out_edges(branch_node, data=True):
            data = edge[2]
            if data['condition'] == True:
                then_edge = edge
            elif data['condition'] == False:
                else_edge = edge

        assert then_edge and else_edge
        return then_edge, else_edge


class BlockReduction(ReductionBase):
    def __init__(self, graph, scope, start_edge=None, start_node=None):
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
        super(BlockReduction, self).__init__(graph, scope)

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
        while not (node is None or node is Exit or isinstance(node, ContinueLoop)):
            if skip_join_check:
                skip_join_check = False
            elif not self._scope.is_reduced_join(node):
                # There are incoming edges that have not been reduced
                # in this scope, so we can't reduce further
                break

            if isinstance(node, Branch):
                node = self._reduce_if(node)

            elif isinstance(node, Loop):
                node = self._reduce_loop(node)

            else:
                assert node == Entry or isinstance(node, Join)
                node = self._traverse_edge(node)

        # Reached a non-reducible node
        self.dest_node = node


    def resolve_tail_nodes(self):
        # Process all tail nodes until all have been reduced.  Since
        # tail nodes might be added during this process, iterate
        # over _tail_reduxes until all nodes are in node_reduxes.

        node_reduxes = {}
        while len(node_reduxes) < len(self._scope._tail_reduxes):
            for node in self._scope._tail_reduxes.keys():
                if node not in node_reduxes:
                    redux = BlockReduction(self._graph, self._scope, start_node=node)
                    node_reduxes[node] = redux

                    if redux.dest_node is Exit:
                        redux.block.stmts.append(Return())
                    else:
                        self._scope.add_tail_redux(redux)

                    break

        # All nodes processed, add them to this block in source code order
        tail_reduxes = sorted(self._scope._tail_reduxes.items(), key = lambda n: n[0].source.from_char)

        node_labels = {}
        for node, reduxes in tail_reduxes:
            if node is Exit:
                label = GotoLabel('__exit', None)
            else:
                if isinstance(node, ContinueLoop):
                    stmt = node.loop.stmt
                else:
                    stmt = node.stmt

                para = stmt.sentence.para
                assert stmt == para.get_first_stmt()
                label = GotoLabel(para.name or '__start', para)

            # Wire source blocks to point to this label
            for redux in reduxes:
                redux.block.stmts.append(Goto(label))
                redux.dest_node = None

            node_labels[node] = label

        for node, reduxes in tail_reduxes:
            redux = node_reduxes[node]
            self.block.stmts.append(node_labels[node])
            self.block.stmts.extend(redux.block.stmts)


    def _add_statements(self, stmts):
        if not self._scope.keep_all_cobol_stmts:
            stmts = suppress_statements(stmts)

        self.block.stmts.extend(stmts)


    def _reduce_if(self, branch):
        if_redux = IfReduction(self._graph, self._scope, branch)
        self.block.stmts.extend(if_redux.block.stmts)
        return if_redux.dest_node


    def _reduce_loop(self, loop):
        loop_redux = LoopReduction(self._graph, self._scope, loop)
        self.block.stmts.extend(loop_redux.block.stmts)
        return loop_redux.dest_node


    def _traverse_edge(self, node):
        n, next, data = self._out_edge(node)
        self._add_statements(data['stmts'])
        return next


class IfReduction(ReductionBase):
    """Reduce a branch into an If object, recursing down the edges.
    """

    def __init__(self, graph, scope, branch_node):
        super(IfReduction, self).__init__(graph, scope)

        then_edge, else_edge = self._out_condition_edges(branch_node)

        self._then = BlockReduction(self._graph, self._scope, start_edge=then_edge)
        self._else = BlockReduction(self._graph, self._scope, start_edge=else_edge)

        self._invert_condition = False
        self._tail_stmts = []

        self._reduce_branches()
        self.block.stmts.append(If(branch_node.stmt,
                                   self._then.block,
                                   self._else.block,
                                   self._invert_condition))
        self.block.stmts.extend(self._tail_stmts)


    def _reduce_branches(self):
        # In a structured if statement the subblocks both lead to the same
        # node, so the block continues there
        if self._then.dest_node == self._else.dest_node:
            self._scope.reduce_join(self._then.dest_node)

            # Flip empty then branches
            if not self._then.block.stmts:
                self._flip_branches()

            self.dest_node = self._then.dest_node
            return

        # Different paths

        # If the else block terminates, flip condition so we can avoid the
        # else branch altogether
        if self._else.dest_node is Exit:
            self._flip_branches()

        # If the then block terminates, merge the else block into this one
        # to reduce the if block
        if self._then.dest_node is Exit:
            self._remove_else_branch()
            self._then.block.stmts.append(Return())
            self._then.dest_node = None
            return

        # Similar logic to terminating blocks, but for loops: if one
        # branch leaves the loop, make it the then_block
        if (self._scope.is_node_main_scope(self._then.dest_node)
            and not self._scope.is_node_main_scope(self._else.dest_node)):
            self._flip_branches()

        if (not self._scope.is_node_main_scope(self._then.dest_node)
            and self._scope.is_node_main_scope(self._else.dest_node)):
            self._remove_else_branch()
            self._scope.add_tail_redux(self._then)
            return

        # Paths diverge and one doesn't exit or leave loop, cannot do
        # anything about them
        self._scope.add_tail_redux(self._then)
        self._scope.add_tail_redux(self._else)


    def _flip_branches(self):
        self._then, self._else = self._else, self._then
        self._invert_condition = True


    def _remove_else_branch(self):
        self.dest_node = self._else.dest_node
        self._tail_stmts = self._else.block.stmts
        self._else.block = Block()


class LoopReduction(ReductionBase):
    """Reduce a Loop node, recursing into the block.
    """
    def __init__(self, graph, parent_scope, loop_node):
        super(LoopReduction, self).__init__(graph, parent_scope)

        self._node = loop_node
        self._scope = LoopReductionScope(parent_scope, loop_node)

        start_edge = self._out_edge(loop_node)

        if self._reduce_while(start_edge):
            return

        self._reduce_forever(start_edge)


    def _reduce_while(self, start_edge):
        """If start_edge fulfils the condition for a while loop, reduce it and return True.

        To be a while loop the first node must be a Branch without any
        preceding statements, one edge of the branch must belong to
        the loop scope (or a sub scope), while the other edge must
        leave the scope into a parent scope without any additional
        statements.  The edge leaving the loop will be the dest node
        for the whole loop.

        """

        src_node, dest_node, edge_data = start_edge

        if not isinstance(dest_node, Branch):
            return False

        if suppress_statements(edge_data['stmts']):
            return False

        then_edge, else_edge = self._out_condition_edges(dest_node)
        invert_condition = False

        then_node = then_edge[1]
        else_node = else_edge[1]

        # Start checking the inverse and flip it if it might qualify
        if self._scope.is_node_scope(else_node) and not self._scope.is_node_scope(then_node):
            then_edge, else_edge = else_edge, then_edge
            then_node, else_node = else_node, then_node
            invert_condition = True

        if not (self._scope.is_node_scope(then_node) and not self._scope.is_node_scope(else_node)):
            # Not a qualifying branch
            return False

        # There cannot be any statements in the else branch for this to be a while loop
        else_data = else_edge[2]
        if suppress_statements(else_data['stmts']):
            return False

        # This is indeed a while branch, so reduce the loop body
        redux = BlockReduction(self._graph, self._scope, start_edge=then_edge)
        self._resolve_continue_reduxes()
        redux.resolve_tail_nodes()

        self.block.stmts.append(While(self._node.stmt.sentence.para, redux.block, dest_node.stmt, invert_condition))
        self.dest_node = else_node

        # Any inner blocks breaking to dest_node are Breaks(), the other are pushed
        # to be tail nodes in the parent scope
        for reduxes in self._scope._break_reduxes.values():
            for r in reduxes:
                if r.dest_node is self.dest_node:
                    self._reduce_break_redux(r)
                else:
                    self._scope._parent.add_tail_redux(r, possible_loop_break=False)

        # Successfully resolved
        return True


    def _reduce_forever(self, start_edge):
        """Reduce a loop that doesn't start with a suitable branch statement
        into a Forever statement.
        """

        redux = BlockReduction(self._graph, self._scope, start_edge=start_edge)
        self._resolve_continue_reduxes()
        redux.resolve_tail_nodes()

        # Infinite loop, unless there's gotos out inside it
        if isinstance(redux.dest_node, ContinueLoop) and redux.dest_node.loop is self._node:
            self.block.stmts.append(Forever(self._node.stmt.sentence.para, redux.block))

        # Loop block terminating somewhere else, let the scope handle it
        else:
            self.dest_node = redux.dest_node
            self._scope.add_tail_redux(self)

        # No blocks breaking into the outer scope, so this cannot be reduced further.
        if not self._scope._break_reduxes:
            return

        # Let the node that most blocks break to be the next node
        # after the loop, and push the others to be tail nodes in the
        # parent scope.

        breaks = sorted(self._scope._break_reduxes.items(), key=lambda n: -len(n[1]))

        self.dest_node, reduxes = breaks[0]
        for r in reduxes:
            self._reduce_break_redux(r)

        for node, reduxes in breaks[1:]:
            for r in reduxes:
                self._scope._parent.add_tail_redux(r, possible_loop_break=False)


    def _resolve_continue_reduxes(self):
        """Handle inner loops that gotos the start of this loop by adding a
        label to the loop as a whole and goto statements to the inner reduxes.
        """
        reduxes = self._scope.pop_continue_node()
        if not reduxes:
            return

        para = self._node.stmt.sentence.para
        assert self._node.stmt == para.get_first_stmt()
        label = GotoLabel(para.name or '__start', para)
        self.block.stmts.append(label)

        for redux in reduxes:
            redux.block.stmts.append(Goto(label))
            redux.dest_node = None


    def _reduce_break_redux(self, redux):
        self._scope._parent.reduce_join(redux.dest_node)
        redux.block.stmts.append(Break())
        redux.dest_node = None

