# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from collections import Counter
import networkx as nx
from .syntax import *
from .structure import *


suppressed_cobol_statements = (GoToStatement, TerminatingStatement, NextSentenceStatement)

def suppress_statements(stmts):
    return [s for s in stmts if not isinstance(s, suppressed_cobol_statements)]


def out_edge(graph, node):
    """Follow a single edge from node, returning a tuple:
    (node, dest_node, edge_data)
    """
    edges = graph.out_edges(node, data=True)
    assert len(edges) == 1
    return edges[0]


def out_condition_edges(graph, branch_node):
    """Follow the condition edges leading out from a branch node, returning a tuple
    (then_edge, else_edge) where each edge is a tuple (node, dest_node, edge_data).
    """

    then_edge = else_edge = None

    for edge in graph.out_edges(branch_node, data=True):
        data = edge[2]
        if data['condition'] == True:
            then_edge = edge
        elif data['condition'] == False:
            else_edge = edge

    assert then_edge and else_edge
    return then_edge, else_edge


class ReductionScopeBase(object):
    """Keeps track of reductions going on in a graph scope.

    There's a root scope for each section, and then a child scope is
    created for each nested loop being reduced.
    """

    def __init__(self, graph, scope_node):
        self._graph = graph

        scope_nodes = set((n for n in graph.nodes_iter() if n.scope is scope_node))

        self._unreduced_nodes = set((n for n in scope_nodes
                                     if not isinstance(n, JumpNodeBase)))

        self._node_in_edge_counts = Counter((dest for src, dest in self._graph.in_edges_iter(scope_nodes)))


    @property
    def root(self):
        raise NotImplementedError()

    @property
    def unreduced_nodes(self):
        """A set of nodes in this scope which haven't yet been reduced.
        """
        return self._unreduced_nodes

    @property
    def node_in_edge_counts(self):
        """A Counter() mapping nodes to the number of in-scope edges to them.
        """
        return self._node_in_edge_counts


class RootReductionScope(ReductionScopeBase):
    """The root redux scope for a section.
    """

    def __init__(self, graph, keep_all_cobol_stmts=False, debug=False):

        super(RootReductionScope, self).__init__(graph, None)
        self._keep_all_cobol_stmts = keep_all_cobol_stmts
        self._debug = debug

        # Create labels for all known goto targets, since this
        # is used while reducing blocks to insert labels at the
        # right places

        self._node_labels = NodeLabelDict()
        for node in self._graph.nodes_iter():
            if isinstance(node, GotoNode):
                self._node_labels.get_or_create(node.node)

    @property
    def root(self):
        return self

    @property
    def keep_all_cobol_stmts(self):
        return self._keep_all_cobol_stmts

    @property
    def debug(self):
        return self._debug

    @property
    def node_labels(self):
        return self._node_labels


    def reduce(self):
        """Reduce a ScopeStructuredGraph into a Block and return it.
        """
        redux = BlockReduction(self._graph, self, start_node=Entry)
        redux.resolve_tail_nodes(Exit)
        return redux.block


class LoopReductionScope(ReductionScopeBase):
    """The redux scope for a loop level.  A scope is created for each Loop
    node.
    """

    def __init__(self, parent, loop):
        super(LoopReductionScope, self).__init__(parent._graph, loop)
        self._root = parent.root
        self._loop = loop

    @property
    def root(self):
        return self._root


class ReductionBase(object):
    """A redux traverses a portion of the graph, attempting to reduce as many
    nodes and edges as possible into a statement Block.
    """

    def __init__(self, graph, scope):
        self._graph = graph
        self._scope = scope
        self._block = Block()
        self._dest_node = None
        self._branch_dests = Counter()


    @property
    def block(self):
        """The statement Block for this redux.
        """
        return self._block


    @property
    def size(self):
        """The size of this redux block and it's children.
        """
        raise NotImplementedError()


    @property
    def dest_node(self):
        """The destination node that the code in the block must continue to.

        If the redux could be completely reduced by adding statements
        to the block, this is set to None.
        """
        return self._dest_node


    @property
    def branch_dests(self):
        """A Counter dict mapping nodes to the number of code branches in this
        scope that leads to them.  Used to determine when all edges to
        a node have been traversed so the node can be flattened.
        """
        return self._branch_dests


    def _out_edge(self, node):
        return out_edge(self._graph, node)

    def _out_condition_edges(self, branch_node):
        return out_condition_edges(self._graph, branch_node)


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
        self._unresolved_if_redux = None
        self._sub_block_size = 0

        if start_edge is not None:
            src, node, data = start_edge
            self._add_statements(data['stmts'])
            skip_node_in_edge_check = False
        else:
            assert start_node is not None
            node = start_node
            skip_node_in_edge_check = True

        # Reduce a sequence of branches or loops if possible by
        # looping as long as all join paths are accounted for
        while not (node is None or isinstance(node, JumpNodeBase)):
            if node not in self._scope.unreduced_nodes:
                break

            if skip_node_in_edge_check:
                # This node was ok to reduce now, but next one may not be
                skip_node_in_edge_check = False
            else:
                # Only follow edge to this node if there's a single in-scope edge to the node.
                if self._scope.node_in_edge_counts[node] != 1:
                    break

            self._scope.unreduced_nodes.discard(node)

            # Resolving a node that is the target of a goto from somewhere, so
            # add a label
            label = self._scope.root.node_labels.get(node)
            if label is not None:
                self.block.stmts.append(label)

            if isinstance(node, Branch):
                node = self._reduce_if(node)
                skip_node_in_edge_check = True

            elif isinstance(node, Loop):
                node = self._reduce_loop(node)

            else:
                assert node == Entry or isinstance(node, Join)
                node = self._traverse_edge(node)

        # Reached a non-reducible node
        if node is not None:
            self._branch_dests[node] += 1

        self._dest_node = node


    @property
    def size(self):
        s = len(self._block.stmts) + self._sub_block_size
        if self._unresolved_if_redux:
            s += self._unresolved_if_redux.size
        return s


    def resolve_dest_node(self, node, is_else_branch=False):
        if self._unresolved_if_redux:
            # Cannot form an else-if if there are other statements
            if self.block.stmts:
                is_else_branch = False

            self._unresolved_if_redux.resolve_branches(node, is_else_branch=is_else_branch)
            self._block.stmts.extend(self._unresolved_if_redux.block.stmts)
            self._dest_node = self._unresolved_if_redux.dest_node
            self._sub_block_size += self._unresolved_if_redux.size
            self._unresolved_if_redux = None

        # No need to insert any jump here
        if self._dest_node is None or self._dest_node is node:
            return

        # Resolve with a jump
        if self._dest_node is Exit:
            self._block.stmts.append(Return())

        elif isinstance(self._dest_node, ContinueLoop):
            self._block.stmts.append(Continue())

        elif isinstance(self._dest_node, LoopExit):
            self._block.stmts.append(Break())

        elif isinstance(self._dest_node, GotoNode):
            label = self._scope.root.node_labels.get_or_create(self._dest_node.node)
            self._block.stmts.append(Goto(label))

        else:
            # An in-scope jump
            label = self._scope.root.node_labels.get_or_create(self._dest_node)
            self._block.stmts.append(Goto(label))


        self._dest_node = None


    def resolve_tail_nodes(self, target_node):
        """Resolve all tail nodes in the scope for this redux.

        These are nodes that couldn't be resolved in a structured way,
        so each such node will be the target of a goto statement.
        """

        if not self._scope.unreduced_nodes:
            self.resolve_dest_node(target_node)
            return

        # Since there are tail nodes, this reduction must end with a jump
        # before those are added to the block

        # TODO: if this does jump to one of the tails, that should be the first
        # to avoid one goto

        self.resolve_dest_node(None)

        # Consume unreduced nodes that are known goto targets
        node_reduxes = {}
        while self._scope.unreduced_nodes:
            for node in self._scope.unreduced_nodes:
                if node in self._scope.root.node_labels:
                    redux = BlockReduction(self._graph, self._scope, start_node=node)
                    node_reduxes[node] = redux
                    redux.resolve_dest_node(None)
                    break
            else:
                assert False, 'There are unreduced nodes without goto labels'

        # All nodes processed, add them to this block in source code order
        for node, redux in sorted(node_reduxes.items(),
                                  key=lambda n: n[0].source.from_char):
            self.block.stmts.extend(redux.block.stmts)


    def _add_statements(self, stmts):
        if not self._scope.root.keep_all_cobol_stmts:
            stmts = suppress_statements(stmts)

        self.block.stmts.extend(stmts)


    def _reduce_if(self, branch):
        if_redux = IfReduction(self._graph, self._scope, branch)

        # Add branch dest counts from the subblocks into this one
        self._branch_dests.update(if_redux.branch_dests)

        # Unstructured if, so see if the sub-blocks have accounted
        # for all edges to some nodes
        resolved_nodes = [(n, c) for n, c in self._branch_dests.items()
                          if c == self._scope.node_in_edge_counts.get(n)]

        # If no nodes are resolved, save this and return to it later from
        # a higher level
        if not resolved_nodes:
            self._unresolved_if_redux = if_redux
            return None

        # Remove the resolved nodes, so they don't resolve in parent scopes too
        for n, c in resolved_nodes:
            del self._branch_dests[n]

        target_node = self._select_resolved_target_node(resolved_nodes)
        if_redux.resolve_branches(target_node)
        self.block.stmts.extend(if_redux.block.stmts)
        self._sub_block_size += if_redux.size

        assert if_redux.dest_node is target_node or if_redux.dest_node is None
        return target_node


    def _reduce_loop(self, loop):
        loop_scope = LoopReductionScope(self._scope, loop)

        if loop.condition:
            start_edge, exit_edge = self._out_condition_edges(loop)
        else:
            start_edge = self._out_edge(loop)

        redux = BlockReduction(self._graph, loop_scope, start_edge=start_edge)
        redux.resolve_tail_nodes(loop.continue_loop)

        if loop.condition:
            self.block.stmts.append(While(loop.stmt.sentence.para,
                                          redux.block,
                                          loop.stmt,
                                          loop.condition))
        else:
            self.block.stmts.append(Forever(loop.stmt.sentence.para, redux.block))

        self._sub_block_size += redux.size

        if loop.loop_exit:
            src, dest, data = self._out_edge(loop.loop_exit)
            return dest
        else:
            return None

    def _traverse_edge(self, node):
        n, next, data = self._out_edge(node)
        self._add_statements(data['stmts'])
        return next


    def _select_resolved_target_node(self, target_counts):
        # If there are non-jump branches, use the must common target node
        # to minimise the number of gotos, and take the first one if there's
        # a tie (to ensure that the code is deterministic)

        node_counts = sorted(((n, c) for n, c in target_counts
                              if not isinstance(n, JumpNodeBase)),
                             key=lambda kv: (kv[1], -kv[0].source.from_char),
                             reverse=True)

        if node_counts:
            return node_counts[0][0]

        # Second, prefer ContinueLoop to other jumps
        node_counts = [n for n, c in target_counts
                       if isinstance(n, ContinueLoop)]

        if node_counts:
            # There should only be one in each scope
            assert len(node_counts) == 1
            return node_counts[0]

        # Third, prefer Gotos
        node_counts = sorted(((n, c) for n, c in target_counts
                              if isinstance(n, GotoNode)),
                             key=lambda kv: kv[1],
                             reverse=True)

        if node_counts:
            # There should only be one in each scope
            assert len(node_counts) == 1
            return node_counts[0][0]

        # Fourth, prefer LoopExit
        node_counts = [n for n, c in target_counts
                       if isinstance(n, LoopExit)]

        if node_counts:
            # There should only be one in each scope
            assert len(node_counts) == 1
            return node_counts[0][0]

        # If nothing else, use Exit
        return Exit


class IfReduction(ReductionBase):
    """Reduce a branch into an If object, recursing down the edges.
    """

    def __init__(self, graph, scope, branch_node):
        super(IfReduction, self).__init__(graph, scope)
        self._branch_node = branch_node
        self._condition = branch_node.condition

        then_edge, else_edge = self._out_condition_edges(branch_node)

        self._then = BlockReduction(self._graph, self._scope, start_edge=then_edge)
        self._else = BlockReduction(self._graph, self._scope, start_edge=else_edge)

        # Just count the dest nodes, they will be resolved by a parent block
        self._branch_dests.update(self._then.branch_dests)
        self._branch_dests.update(self._else.branch_dests)


    @property
    def size(self):
        # Don't return length of block, since that would
        # double count any statements from a removed else branch
        # in the parent redux.
        return 1 + self._then.size + self._else.size


    def resolve_branches(self, target_node, is_else_branch=False):
        assert self._dest_node is None

        self._then.resolve_dest_node(target_node)
        self._else.resolve_dest_node(target_node, is_else_branch=True)

        assert self._then.dest_node is None or self._then.dest_node is target_node
        assert self._else.dest_node is None or self._else.dest_node is target_node

        # Determine the least costly reduction of the if statement
        strategies = [s for s in (s(self._then, self._else, is_else_branch)
                                  for s in if_reduction_strategies)
                      if s.possible]
        strategies.sort(key=lambda s: s.cost)

        if self._scope.root.debug:
            self._branch_node.stmt.comment = 'cobolsharp: if reduction strategies:\n{}'.format(
                '\n'.join(['   {}'.format(r) for r in strategies]))

        if strategies:
            s = strategies[0]
        else:
            s = NullIfStrategy(self._then, self._else, is_else_branch)

        s.apply()
        if s.flip:
            self._flip_branches()

        if s.remove_else:
            self._dest_node = self._else.dest_node
            tail_stmts = self._else.block.stmts
            self._else._block = Block()
        else:
            self._dest_node = self._then.dest_node or self._else.dest_node
            tail_stmts = ()

        self.block.stmts.append(If(self._branch_node.stmt,
                                   self._condition,
                                   self._then.block,
                                   self._else.block))
        self.block.stmts.extend(tail_stmts)


    def _flip_branches(self):
        self._then, self._else = self._else, self._then
        self._condition = self._condition.invert()



class IfReductionStrategyBase(object):
    # Fixed cost of inverting an if condition
    invert_condition_cost = 5

    # Cost of losing an if-else
    losing_if_else_cost = 20

    # Cost of keeping an else branch when then ends with a jump
    unnecessary_then_jump_cost = 5


    def __init__(self, then_redux, else_redux, is_else_branch):
        self._then = then_redux
        self._else = else_redux
        self._is_else_branch = is_else_branch

    def __repr__(self):
        return '<{} cost {}>'.format(self.__class__.__name__, self.cost)

    def _jump_cost(self, dest_node):
        if dest_node is Exit:
            return 10

        elif isinstance(dest_node, LoopExit):
            return 10

        elif isinstance(dest_node, ContinueLoop):
            return 20

        else:
            return 50

    @property
    def possible(self):
        """Boolean indicating if the reduction is possible."""
        return True

    @property
    def cost(self):
        """The cost of this reduction.
        """
        raise NotImplementedError()

    @property
    def flip(self):
        """True if the branches should be flipped.
        """
        return False

    @property
    def remove_else(self):
        return False

    def apply(self):
        """Apply the strategy to the then/else reduxes.
        """
        pass


class NullIfStrategy(IfReductionStrategyBase):
    """Do no changes to the if statement.
    """

    @property
    def possible(self):
        if not self._then.block.stmts:
            # Not acceptable to have an empty then branch
            return False

        return True

    @property
    def cost(self):
        if len(self._else.block.stmts) == 1 and isinstance(self._else.block.stmts[0], If):
            # Will be an else-if, so no cost of indenting the else
            cost = self._then.size
        else:
            cost = self._then.size + self._else.size

        if self._then.dest_node is None:
            cost += self.unnecessary_then_jump_cost

        return cost


class RemoveElseIfStrategy(IfReductionStrategyBase):
    """Remove the else branch if the then branch terminates.
    """

    @property
    def possible(self):
        return self._then.dest_node is None

    @property
    def cost(self):
        cost = self._then.size
        if self._is_else_branch:
            cost += self.losing_if_else_cost
        return cost

    @property
    def remove_else(self):
        return True


class FlipToRemoveElseStrategy(IfReductionStrategyBase):
    @property
    def possible(self):
        if self._else.dest_node is None:
            # Can remove then branch after flip
            return True

        if not self._then.block.stmts:
            # There won't be any else branch
            return True

        return False

    @property
    def cost(self):
        cost = self._else.size + self.invert_condition_cost
        if self._is_else_branch:
            cost += self.losing_if_else_cost
        return cost

    @property
    def flip(self):
        return True

    @property
    def remove_else(self):
        return True

class JumpFromThenStrategy(IfReductionStrategyBase):
    @property
    def possible(self):
        return self._then.dest_node is not None

    @property
    def cost(self):
        cost = self._then.size + self._jump_cost(self._then.dest_node)
        if self._is_else_branch:
            cost += self.losing_if_else_cost
        return cost

    @property
    def remove_else(self):
        return True

    def apply(self):
        # Re-resolve forcing in a jump
        self._then.resolve_dest_node(None)


class JumpFromFlippedElseStrategy(IfReductionStrategyBase):
    @property
    def possible(self):
        return self._else.dest_node is not None

    @property
    def cost(self):
        cost = self._else.size + self._jump_cost(self._else.dest_node)
        cost += self.invert_condition_cost
        if self._is_else_branch:
            cost += self.losing_if_else_cost
        return cost

    def apply(self):
        # Re-resolve forcing in a jump
        self._else.resolve_dest_node(None)

    @property
    def flip(self):
        return True

    @property
    def remove_else(self):
        return True


if_reduction_strategies = [
    NullIfStrategy,
    RemoveElseIfStrategy,
    FlipToRemoveElseStrategy,
    JumpFromThenStrategy,
    JumpFromFlippedElseStrategy]


class NodeLabelDict(dict):
    def get_or_create(self, node):
        label = self.get(node)
        if label is not None:
            return label

        stmt = node.stmt
        para = stmt.sentence.para

        # TODO: we'd like this to be true, but may not be able to
        # reduce all goto tangles properly:
        # assert stmt == para.get_first_stmt()

        if stmt == para.get_first_stmt() and para.name:
            label = GotoLabel(para.name, para)
        else:
            label = GotoLabel('__line{}'.format(stmt.source.from_line), None)

        label.scope = node.scope
        self[node] = label

        return label
