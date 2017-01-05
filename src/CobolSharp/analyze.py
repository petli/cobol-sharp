# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import networkx as nx
from .syntax import *
from .structure import *


suppressed_cobol_statements = (GoToStatement, TerminatingStatement, NextSentenceStatement)

def suppress_statements(stmts):
    return [s for s in stmts if not isinstance(s, suppressed_cobol_statements)]


class ReductionScopeBase(object):
    """Keeps track of reductions going on in a graph scope.

    There's a root scope for each section, and then a child scope is
    created for each nested loop being reduced.
    """

    def __init__(self, graph, scope_node):
        self._graph = graph

        self._nodes = set((n for n,d in graph.nodes_iter(data=True)
                           if d.get('scope') is scope_node))

        self._unreduced_nodes = set((n for n in self._nodes
                                     if not (isinstance(n, ContinueLoop)
                                             or n is Entry
                                             or n is Exit)))

        # Map from join node to a count of the number of reduced in edges to that join in this scope
        self._reduced_joins = {}
        self._tail_nodes = set()


    @property
    def root(self):
        raise NotImplementedError()

    @property
    def unreduced_nodes(self):
        """A set of nodes in this scope which haven't yet been reduced.
        """
        return self._unreduced_nodes

    @property
    def tail_nodes(self):
        """A set of nodes in this scope which must be reduced in the tail of the scope.
        """
        return self._tail_nodes


    def resolve_jump_redux(self, redux, loop_jump=True):
        """Resolve a redux that might have to finish with a jump of some kind
        (return, continue, break or at worst goto).
        """

        if redux.dest_node is None:
            return

        if redux.dest_node is Exit:
            redux.add_jump_stmt(Return())
            return

        # If the goto is within the same scope, queue up
        # this node for reduction in the tail of the scope
        if self.is_node_main_scope(redux.dest_node):
            self._tail_nodes.add(redux.dest_node)

        label = self.root.get_node_goto_label(redux.dest_node)
        redux.add_jump_stmt(Goto(label))


    def reduce_join(self, node):
        """Increase the count of reduced in edges to a Join node.
        """
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
        no parent scope that the node also belongs to.
        """
        return node is not None and node in self._nodes


    def is_node_scope(self, node):
        """Return True if the node belongs to this scope or a child scope.
        """
        raise NotImplementedError()


class RootReductionScope(ReductionScopeBase):
    """The root redux scope for a section.
    """

    def __init__(self, graph, keep_all_cobol_stmts=False):
        super(RootReductionScope, self).__init__(graph, None)
        self._keep_all_cobol_stmts = keep_all_cobol_stmts
        self._node_goto_labels = {}

    @property
    def root(self):
        return self

    @property
    def keep_all_cobol_stmts(self):
        return self._keep_all_cobol_stmts


    def has_node_goto_label(self, node):
        return node in self._node_goto_labels


    def get_node_goto_label(self, node):
        """Get a GotoLabel for a given node, constructing it if necessary.
        """

        label = self._node_goto_labels.get(node)
        if label is None:
            if isinstance(node, ContinueLoop):
                stmt = node.loop.stmt
            else:
                stmt = node.stmt

            para = stmt.sentence.para

            # TODO: we'd like this to be true, but may not be able to
            # reduce all goto tangles properly:
            # assert stmt == para.get_first_stmt()

            if stmt == para.get_first_stmt() and para.name:
                label = GotoLabel(para.name, para)
            else:
                label = GotoLabel('__line{}'.format(stmt.source.from_line), None)

            self._node_goto_labels[node] = label

        return label


    def is_node_scope(self, node):
        # Root scope covers all nodes
        return True


class LoopReductionScope(ReductionScopeBase):
    """The redux scope for a loop level.  A scope is created for each Loop
    node.
    """

    def __init__(self, parent, loop):
        super(LoopReductionScope, self).__init__(parent._graph, loop)
        self._parent = parent
        self._root = parent.root
        self._loop = loop
        self._break_reduxes = {}

    @property
    def root(self):
        return self._root

    @property
    def parent(self):
        """The parent scope."""
        return self._parent

    @property
    def break_reduxes(self):
        """A break redux is similar to a tail redux, but its dest node belongs
        to the parent scope and can thus be reduced with a break statement.

        This is a dictionary where the key is a dest node and the
        value is a list of ReductionBase objects that points to that
        node.
        """
        return self._break_reduxes


    def resolve_jump_redux(self, redux, loop_jump=True):
        if redux.dest_node is None:
            return

        # Can it be resolved with a continue in the same scope
        if loop_jump and isinstance(redux.dest_node, ContinueLoop) and redux.dest_node.loop is self._loop:
            redux.add_jump_stmt(Continue())

        # Or if this might be a break into the parent scope instead of a goto,
        # queue it up until the loop reduction is finished
        elif loop_jump and self._parent.is_node_main_scope(redux.dest_node):
            reduxes = self._break_reduxes.get(redux.dest_node)
            if reduxes is not None:
                reduxes.append(redux)
            else:
                self._break_reduxes[redux.dest_node] = [redux]

        # Handle in scope
        elif self.is_node_main_scope(redux.dest_node):
            super(LoopReductionScope, self).resolve_jump_redux(redux)

        # Let parent handle it
        else:
            self._parent.resolve_jump_redux(redux, loop_jump=False)


    def reduce_inner_edge(self, node):
        if node in self._nodes:
            super(LoopReductionScope, self).reduce_inner_edge(node)
        else:
            self.parent.reduce_inner_edge(node)


    def is_node_scope(self, node):
        return node is not None and self._loop in self._graph.node[node].get('scopes', ())


class ReductionBase(object):
    """A redux traverses a portion of the graph, attempting to reduce as many
    nodes and edges as possible into a statement Block.
    """

    def __init__(self, graph, scope):
        self._graph = graph
        self._scope = scope
        self._block = Block()
        self._dest_node = None

    @property
    def block(self):
        """The statement Block for this redux.
        """
        return self._block


    @property
    def dest_node(self):
        """The destination node that the code in the block must continue to.

        If the redux could be completely reduced by adding statements
        to the block, this is set to None.
        """
        return self._dest_node


    def add_jump_stmt(self, stmt):
        """Add a jump statement to the end of the reduction block.
        """
        assert self.dest_node is not None
        self._block.stmts.append(stmt)
        self._dest_node = None


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
    """A reduction of a structured section of the graph into a single block.

    This is a recursive operation that reduces blocks in contained
    branch or loop statements into their own blocks, which are
    then folded into this block until nothing more can be reduced.
    """

    def __init__(self, graph, scope, start_edge=None, start_node=None):
        """If start_edge is not None, start_node must have a single out edge
        which is the start of the block.  Otherwise start_edge is the
        starting edge which is used for the traversal.
        """

        super(BlockReduction, self).__init__(graph, scope)

        if start_edge is not None:
            src, node, data = start_edge
            self._add_statements(data['stmts'])
            skip_start_node_check = False
        else:
            assert start_node is not None
            node = start_node
            skip_start_node_check = True

        # Reduce a sequence of branches or loops if possible by
        # looping as long as all join paths are accounted for
        while not (node is None or node is Exit or isinstance(node, ContinueLoop)):
            if skip_start_node_check:
                skip_start_node_check = False
            else:
                # Don't go outside the scope
                if not self._scope.is_node_main_scope(node):
                    break

                # There are incoming in-scope edges that have not been reduced
                # in this scope, so we can't reduce further
                if not self._scope.is_reduced_join(node):
                    break

                # Node has already been processed (TODO: should this be an assert?)
                if node not in self._scope.unreduced_nodes:
                    break

            self._scope.unreduced_nodes.discard(node)

            # Resolving a node that is the target of a goto from somewhere, so
            # add a label
            if self._scope.root.has_node_goto_label(node):
                label = self._scope.root.get_node_goto_label(node)
                self.block.stmts.append(label)

            # If it was a local tail node, do it here instead
            self._scope.tail_nodes.discard(node)

            if isinstance(node, Branch):
                node = self._reduce_if(node)

            elif isinstance(node, Loop):
                node = self._reduce_loop(node)

            else:
                assert node == Entry or isinstance(node, Join)
                node = self._traverse_edge(node)

        # Reached a non-reducible node
        self._dest_node = node


    def resolve_tail_nodes(self):
        """Resolve all tail nodes in the scope for this redux.

        These are nodes that couldn't be resolved in a structured way,
        so each such node will be the target of a goto statement.
        """

        # Any unvisited nodes at this point are also tail nodes
        self._scope.tail_nodes.update(self._scope.unreduced_nodes)

        if not self._scope.tail_nodes:
            return

        # Since there are tail nodes, this reduction must end with a jump
        # before those are added to the block
        self._scope.resolve_jump_redux(self)

        # Process all tail nodes until all have been reduced.  Since
        # tail nodes might be added during this process, iterate
        # until _tail_nodes is empty

        node_reduxes = {}
        while self._scope.tail_nodes:
            node = self._scope.tail_nodes.pop()
            if node not in node_reduxes:
                redux = BlockReduction(self._graph, self._scope, start_node=node)
                node_reduxes[node] = redux
                self._scope.resolve_jump_redux(redux)

        # All nodes processed, add them to this block in source code order
        for node, redux in sorted(node_reduxes.items(),
                                  key=lambda n: n[0].source.from_char):
            assert redux.dest_node is None

            # Ensure label exists
            self._scope.root.get_node_goto_label(node)
            self.block.stmts.extend(redux.block.stmts)


    def _add_statements(self, stmts):
        if not self._scope.root.keep_all_cobol_stmts:
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

            # Flip empty then branches to avoid an unnecessary else
            if not self._then.block.stmts:
                self._flip_branches()

            self._dest_node = self._then.dest_node
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
            self._then.add_jump_stmt(Return())
            return

        # Similar logic to terminating blocks, but for loops: if one
        # branch leaves the loop, make it the then_block
        if (self._scope.is_node_main_scope(self._then.dest_node)
            and not self._scope.is_node_main_scope(self._else.dest_node)):
            self._flip_branches()

        if (not self._scope.is_node_main_scope(self._then.dest_node)
            and self._scope.is_node_main_scope(self._else.dest_node)):
            self._remove_else_branch()
            self._scope.resolve_jump_redux(self._then)
            return

        # Similar logic to terminating blocks, but for loops: if one
        # branch continues to the start of the loop, make it the then_block
        if (isinstance(self._else.dest_node, ContinueLoop)
            and self._scope.is_node_main_scope(self._else.dest_node)):
            self._flip_branches()

        if (isinstance(self._then.dest_node, ContinueLoop)
            and self._scope.is_node_main_scope(self._then.dest_node)):
            self._remove_else_branch()
            self._then.add_jump_stmt(Continue())
            return

        # Paths diverge and one doesn't exit or leave loop, cannot do
        # anything about them
        self._scope.resolve_jump_redux(self._then)
        self._scope.resolve_jump_redux(self._else)


    def _flip_branches(self):
        self._then, self._else = self._else, self._then
        self._invert_condition = True


    def _remove_else_branch(self):
        self._dest_node = self._else.dest_node
        self._tail_stmts = self._else.block.stmts
        self._else._block = Block()


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
        # TODO: well, it can, but it makes it impossible to add Break() statements.
        else_data = else_edge[2]
        if suppress_statements(else_data['stmts']):
            return False

        # This is indeed a while branch, so reduce the loop body
        self._scope.unreduced_nodes.remove(dest_node)

        redux = BlockReduction(self._graph, self._scope, start_edge=then_edge)
        redux.resolve_tail_nodes()

        self.block.stmts.append(While(self._node.stmt.sentence.para, redux.block, dest_node.stmt, invert_condition))
        self._dest_node = else_node

        # Any inner blocks breaking to dest_node are Breaks(), the other become gotos
        for reduxes in self._scope.break_reduxes.values():
            for r in reduxes:
                if r.dest_node is self.dest_node:
                    self._reduce_break_redux(r)
                else:
                    self._scope.resolve_jump_redux(r, loop_jump=False)

        # Successfully resolved
        return True


    def _reduce_forever(self, start_edge):
        """Reduce a loop that doesn't start with a suitable branch statement
        into a Forever statement.
        """

        redux = BlockReduction(self._graph, self._scope, start_edge=start_edge)
        redux.resolve_tail_nodes()

        self.block.stmts.append(Forever(self._node.stmt.sentence.para, redux.block))

        # No blocks breaking into the outer scope, so this cannot be reduced further.
        if not self._scope.break_reduxes:
            return

        # Let the node that most blocks break to be the next node
        # after the loop, and push the others to be tail nodes in the
        # parent scope.

        breaks = sorted(self._scope.break_reduxes.items(), key=lambda n: -len(n[1]))

        self._dest_node, reduxes = breaks[0]
        for r in reduxes:
            self._reduce_break_redux(r)

        for node, reduxes in breaks[1:]:
            for r in reduxes:
                self._scope.resolve_jump_redux(r, loop_jump=False)


    def _reduce_break_redux(self, redux):
        self._scope.parent.reduce_join(redux.dest_node)
        redux.block.stmts.append(Break())
        redux._dest_node = None

