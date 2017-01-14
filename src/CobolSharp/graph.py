# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from collections import defaultdict

import networkx as nx
import pydotplus

from .syntax import *
from .structure import *
from .analyze import *

# These are used to make node scopes more visible in scope graphs
node_scope_colors = [
    'blue',
    'red',
    'green',
    'purple',
    'lightblue'
    'orange',
    'cyan',
    'magenta',
]

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
        graph = cls()

        for para in section.paras.values():
            for sentence in para.sentences:
                for stmt in sentence.stmts:
                    if isinstance(stmt, SequentialStatement):
                        graph._add_edge(stmt, stmt.next_stmt)

                    elif isinstance(stmt, BranchStatement):
                        graph._add_edge(stmt, stmt.true_stmt, condition=True)
                        graph._add_edge(stmt, stmt.false_stmt, condition=False)

                    elif isinstance(stmt, TerminatingStatement):
                        graph._add_edge(stmt, Exit)

                    else:
                        raise RuntimeError('Unexpected statement type: {}'.format(stmt))

        graph._add_edge(Entry, section.get_first_stmt())

        return graph

    def _add_edge(self, src, dest, **attr):
        if dest is None:
            dest = Exit
        self.graph.add_edge(src, dest, attr)

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


class StructureGraphBase(object):
    def __init__(self, debug=False):
        self.graph = nx.MultiDiGraph()
        self._debug = debug

    def print_nodes(self):
        nodes = self.graph.nodes()
        nodes.sort(key = lambda n: n.source.from_char)
        for node in nodes:
            print('{} [loop {}]'.format(node, node.scope))
            for n, next_node, data in self.graph.out_edges_iter(node, data=True):
                if data.get('condition') == True:
                    print('True:')
                elif data.get('condition') == False:
                    print('False:')

                for stmt in data['stmts']:
                    print(stmt)

                print('-> {}'.format(next_node))


    def write_dot(self, output_path):
        """Write a graphviz .dot representation of the graph to output_path.
        """

        # Write the graph ourselves to output statements as edge labels

        dot = pydotplus.Dot('', graph_type='digraph', strict=False)
        dot.set_edge_defaults(labeljust='l')

        added_nodes = set()

        scope_colors = defaultdict(
            lambda: node_scope_colors[len(scope_colors) % len(node_scope_colors)])

        for src, dest, data in self.graph.edges_iter(data=True):
            src_id = str(id(src))
            dest_id = str(id(dest))

            if src_id not in added_nodes:
                added_nodes.add(src_id)
                dot.add_node(pydotplus.Node(src_id, label=str(src), color=scope_colors[src.scope]))

            if dest_id not in added_nodes:
                added_nodes.add(dest_id)
                dot.add_node(pydotplus.Node(dest_id, label=str(dest), color=scope_colors[src.scope]))

            stmts = data['stmts']
            condition = data.get('condition')

            label = ''
            if condition is not None:
                label = 'if {}:\n'.format(condition)

            label += '\n'.join((str(s) for s in stmts))

            if label:
                dot.add_edge(pydotplus.Edge(src_id, dest_id, label=label))
            else:
                dot.add_edge(pydotplus.Edge(src_id, dest_id))

        with open(output_path, mode='wt', encoding='utf-8') as f:
            f.write(dot.to_string())


class CobolStructureGraph(StructureGraphBase):
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

    @classmethod
    def from_stmt_graph(cls, stmt_graph):
        cobol_graph = cls()

        branch_nodes = []
        join_nodes = []
        node_stmts = {}

        # Find all stmts that are branches or joins and wrap them
        for stmt in stmt_graph.graph:
            if isinstance(stmt, BranchStatement):
                n = Branch(stmt)
                branch_nodes.append(n)
                node_stmts[stmt] = n

            elif isinstance(stmt, TerminatingStatement):
                node_stmts[stmt] = Exit

            elif stmt is Exit:
                node_stmts[Exit] = Exit

            elif stmt_graph.graph.in_degree(stmt) > 1:
                n = Join(stmt)
                join_nodes.append(n)
                node_stmts[stmt] = n

        # Add statements from Entry node
        nbrs = stmt_graph.graph.successors(Entry)
        assert len(nbrs) == 1
        cobol_graph._add_branch_edge(stmt_graph, node_stmts, Entry, nbrs[0])

        # Add statements from each Branch node
        for node in branch_nodes:
            cobol_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt.true_stmt, condition=True)
            cobol_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt.false_stmt, condition=False)

        # Add statements from all join nodes,
        for node in join_nodes:
            # Temporarily drop it to avoid detecting false self-loop
            del node_stmts[node.stmt]
            cobol_graph._add_branch_edge(stmt_graph, node_stmts, node, node.stmt)
            node_stmts[node.stmt] = node

        return cobol_graph


    def _add_branch_edge(self, stmt_graph, node_stmts, source_node, start_stmt, **attrs):
        stmt = start_stmt or Exit
        stmts = []
        dest_node = None

        while stmt not in node_stmts:
            stmts.append(stmt)
            nbrs = stmt_graph.graph.successors(stmt)
            assert len(nbrs) == 1
            stmt = nbrs[0]

            if stmt is start_stmt:
                # This is a self-loop
                dest_node = source_node
                break

        if dest_node is None:
            dest_node = node_stmts[stmt]

        attrs['stmts'] = stmts
        self.graph.add_edge(source_node, dest_node, attr_dict=attrs)



class AcyclicStructureGraph(StructureGraphBase):
    """Similar to a CobolStructureGraph, but loops are broken up by adding
    Loop and ContinueLoop nodes to produce a DAG.

    A Loop node identifies the start of a loop.  It replaces a Join
    node, and is put in front of other nodes.

    All edges that pointed to the original join node is replaced by an
    edge to a ContinueLoop node that references the Loop node object.

    Each node in a loop will have two attributes:
      - 'scopes': a set of all the Loop objects it belongs to
      - 'scope': the inner-most Loop object it belongs to

    The Loop object itself does not belong to the loop, since it will
    be replaced by a statement that wraps the loop statements.
    """

    def __init__(self, *args, **kwargs):
        super(AcyclicStructureGraph, self).__init__(*args, **kwargs)
        self._loops = []


    @classmethod
    def from_cobol_graph(cls, cobol_graph):
        """Identify loops in a CobolStructureGraph and break them by adding Loop
        and ContinueLoop nodes.  Returns the resulting AcyclicStructureGraph.
        """
        dag = cls()

        # Copy by way of edges, to avoid getting copies of the node objects
        dag.graph.add_edges_from(cobol_graph.graph.edges(keys=True, data=True))

        # Loops are strongly connected components, i.e. a set of nodes
        # which can all reach the other ones via some path through the
        # component.

        # Since loops can contain loops, this is done repeatedly until all
        # loops have been broken.  At this stage single-node loops are ignored,
        # since nx.strongly_connected_components() returns components also
        # consisting of a single nodes without any self-looping edge.
        while True:
            components = [c for c in nx.strongly_connected_components(dag.graph)
                          if len(c) > 1]
            if not components:
                break

            for component in components:
                dag._break_component_loop(component)

        # Finally find any remaining single-node loops
        for node in list(dag.graph):
            if dag.graph[node].get(node) is not None:
                dag._break_component_loop({node})

        return dag


    def _break_component_loop(self, component):

        start_node = self._find_loop_start(component)

        loop = Loop(start_node.stmt)
        loop.scope = start_node.scope
        self._loops.append(loop)

        continue_loop = ContinueLoop(loop)
        continue_loop.scope = loop
        loop.continue_loop = continue_loop

        for node in component:
            node.scope = loop

        # Break in-loop edges to the start node, and redirect out-of-loop edges to the loop node
        for edge in self.graph.in_edges(start_node, data=True, keys=True):
            src, dest, key, data = edge
            self.graph.remove_edge(src, dest, key)

            if src in component:
                self.graph.add_edge(src, continue_loop, key, data)
            else:
                self.graph.add_edge(src, loop, key, data)

        if isinstance(start_node, Join):
            # Replace Join node
            for edge in self.graph.out_edges(start_node, data=True, keys=True):
                src, dest, key, data = edge
                self.graph.remove_edge(src, dest, key)
                self.graph.add_edge(loop, dest, key, data)

            self.graph.remove_node(start_node)
        else:
            # Wire to first node in loop
            assert isinstance(start_node, (Loop, Branch))
            self.graph.add_edge(loop, start_node, stmts=[])


    def _find_loop_start(self, component):
        # The node with the most in edges from the rest of the graph
        # is considered the loop start
        return max(component, key = lambda node: sum((
            1 for pred in self.graph.predecessors_iter(node)
            if pred not in component)))


class ScopeStructuredGraph(StructureGraphBase):
    """An structured graph that has been analysed to isolate scopes
    (i.e. nested loops) by removing cross-scope edges.  The purpose is
    to get a structured graph that can easily be flattened into linear
    code.

    This identifies conditional loops and replaces such Loop nodes
    with ConditionalLoop objects.  A ConditionalLoop always have a
    condition=False edge leading to the LoopExit node, while the
    condition=True edge leads to the nodes in the loop.

    All cross-scope edges are processed to ensure they go to either a
    LoopExit or a GotoLabel node:

    - The best candidate node for the exit of a Loop scope is
      identified and the edges from the inner loop to this node is
      replaced by edges to a LoopExit node in the parent scope.  This
      LoopExit node has a single edge to the target node.

    - ContinueLoop nodes that cross scopes are replaced by regular
      jumps.

    - Edges that crosses scopes (excluding edges from Loop nodes, or
      to Exit or LoopExit nodes) are replaced by edges to new GotoNode
      nodes in the source scope.
    """

    def __init__(self, *args, **kwargs):
        super(ScopeStructuredGraph, self).__init__(*args, **kwargs)

        # Map (scope, dest) node -> GotoNode objects
        self._goto_nodes = {}


    def flatten_block(self, keep_all_cobol_stmts=False):
        """Translate the graph structure to a Block of CobolStatement or
        structure elements and return it.
        """
        scope = RootReductionScope(self.graph, keep_all_cobol_stmts, debug=self._debug)
        block = scope.reduce()
        return block


    @classmethod
    def from_acyclic_graph(cls, acyclic_graph, debug=False):
        scope_graph = cls(debug=debug)

        # Copy by way of edges, to avoid getting copies of the node objects
        scope_graph.graph.add_edges_from(acyclic_graph.graph.edges(keys=True, data=True))

        # Find nodes that are LoopExits
        for loop in acyclic_graph._loops:
            if not scope_graph._find_conditional_loop(loop):
                scope_graph._find_loop_exit(loop)

        # Drop cross-scope ContinueLoops
        for node in scope_graph.graph.nodes():
            if isinstance(node, ContinueLoop):
                scope_graph._continue_to_goto(node)

        # Identify all cross-scope gotos
        for edge in scope_graph.graph.edges(keys=True, data=True):
            src, dest, key, data = edge
            if not (dest is Exit
                    or isinstance(src, Loop)
                    or isinstance(dest, LoopExit)
                    or src.scope is dest.scope):
                scope_graph._goto_node(src, dest, key, data)

        return scope_graph


    def _find_conditional_loop(self, loop):
        """Identify a conditional Loop and its LoopExit.  Returns True if such
        a loop was found, False otherwise.

        To be a conditional loop the first node must be a Branch
        without any preceding statements, one edge of the branch must
        belong to the loop scope, while the other edge must leave the
        scope without any additional statements.  The dest node of the
        edge leaving the loop will be the LoopExit.
        """

        src, dest, data = out_edge(self.graph, loop)

        if not isinstance(dest, Branch):
            return False

        if suppress_statements(data['stmts']):
            return False

        branch = dest
        condition = branch.condition
        then_edge, else_edge = out_condition_edges(self.graph, branch)
        then_node = then_edge[1]
        else_node = else_edge[1]

        # Start checking the inverse and flip it if it might qualify
        if else_node.scope is loop and then_node.scope is not loop:
            then_edge, else_edge = else_edge, then_edge
            then_node, else_node = else_node, then_node
            condition = condition.invert()

        if not (then_node.scope is loop and else_node.scope is not loop):
            # Not a qualifying branch
            return False

        then_data = then_edge[2]
        else_data = else_edge[2]

        # There cannot be any statements in the else branch for this to be a while loop
        if suppress_statements(else_data['stmts']):
            return False

        loop.condition = condition

        loop_exit = LoopExit(loop)
        loop_exit.scope = else_node.scope
        loop.loop_exit = loop_exit

        # Remove the branch and move the edges to the loop node
        self.graph.remove_node(branch)
        self.graph.add_edge(loop, then_node, stmts=then_data['stmts'], condition=True)
        self.graph.add_edge(loop, loop_exit, stmts=[], condition=False)

        # Move any other loop scope edges to the else node to the loop exit node
        for src, dest, key, data in self.graph.in_edges(else_node, keys=True, data=True):
            if src.scope is loop:
                self.graph.remove_edge(src, dest, key)
                self.graph.add_edge(src, loop_exit, key, data)

        self.graph.add_edge(loop_exit, else_node, stmts=[])

        return True


    def _find_loop_exit(self, loop):
        # Map from exit nodes to their in edges from this loop scope
        exit_edges = defaultdict(list)

        for edge in self.graph.edges_iter(keys=True, data=True):
            src, dest, key, data = edge
            if dest is not Exit and src.scope is loop and dest.scope is loop.scope:
                exit_edges[dest].append(edge)

        if not exit_edges:
            # No loop exits
            return

        def exit_weight(kv):
            dest = kv[0]
            edges = kv[1]

            # Use mot popular destination
            weight = len(edges)

            # Prioritise non-jumps
            if not isinstance(dest, JumpNodeBase):
                weight *= 10

            # Break ties by jumping the shortest distance possible
            weight += 1.0 / abs(dest.source.from_char - loop.source.from_char)
            return weight

        exits = sorted(exit_edges.items(), key=exit_weight, reverse=True)
        exit_node = exits[0][0]
        edges = exits[0][1]

        loop_exit = LoopExit(loop)
        loop_exit.scope = exit_node.scope
        loop.loop_exit = loop_exit

        self.graph.add_edge(loop_exit, exit_node, stmts=[])

        for src, dest, key, data in edges:
            self.graph.remove_edge(src, dest, key)
            self.graph.add_edge(src, loop_exit, key, data)

        if self._debug:
            loop.stmt.comment = 'cobolsharp: loop exit candidates:\n{}'.format(
                '\n'.join(['   {}'.format(x[0]) for x in exits]))


    def _continue_to_goto(self, continue_node):
        """Change all in edges to a ContinueLoop that crosses scope to point
        directly to the loop instead.  In the next step it will be
        turned into a GotoLabel edge.
        """

        edges = self.graph.in_edges(continue_node, keys=True, data=True)
        for src, dest, key, data in edges:
            if src is not continue_node.loop and src.scope is not continue_node.loop:
                self.graph.remove_edge(src, dest, key)
                self.graph.add_edge(src, continue_node.loop, key, data)

        # Remove the continue if it was all turned into gotos
        if self.graph.in_degree(continue_node) == 0:
            continue_node.loop.continue_node = None
            self.graph.remove_node(continue_node)


    def _goto_node(self, src, dest, key, data):
        """Change a cross-scope edge to a GotoNode().
        """

        goto_node = self._goto_nodes.get((src.scope, dest))
        if goto_node is None:
            goto_node = GotoNode(dest)
            goto_node.scope = src.scope
            self._goto_nodes[(src.scope, dest)] = goto_node

        self.graph.remove_edge(src, dest, key)
        self.graph.add_edge(src, goto_node, key, data)
