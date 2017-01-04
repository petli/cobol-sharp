# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

import networkx as nx
from pygraphviz import AGraph

from .syntax import *
from .structure import *
from .analyze import BlockReduction, RootReductionScope

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


    def _add_branch_edge(self, stmt_graph, node_stmts, source_node, start_stmt, **attrs):
        stmt = start_stmt
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


    def print_nodes(self):
        nodes = self.graph.nodes()
        nodes.sort(key = lambda n: n.source.from_char)
        for node in nodes:
            loops = self.graph.node[node].get('loops', ())
            print('{} [{}]'.format(node, ', '.join([str(loop) for loop in loops])))
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

        # Since the edge attributes are lost by
        # nx.nx_agraph.write_dot(), transfer everything to an AGraph
        # ourselves.

        ag = AGraph(directed=True, strict=False, labeljust='l')

        for src, dest, data in self.graph.edges_iter(data=True):
            src_id = str(id(src))
            dest_id = str(id(dest))

            if src_id not in ag:
                ag.add_node(src_id, label=str(src))

            if dest_id not in ag:
                ag.add_node(dest_id, label=str(dest))

            stmts = data['stmts']
            condition = data.get('condition')

            label = ''
            if condition is not None:
                label = 'if {}:\n'.format(condition)

            label += '\n'.join((str(s) for s in stmts))


            if label:
                ag.add_edge(src_id, dest_id, label=label)
            else:
                ag.add_edge(src_id, dest_id)

        ag.write(output_path)


class AcyclicBranchGraph(BranchJoinGraph):
    """Similar to a BranchJoinGraph, but loops are broken up by adding
    Loop and ContinueLoop nodes to produce a DAG.

    A Loop node identifies the start of a loop.  It replaces a Join
    node, and is put in front of other nodes.

    All edges that pointed to the original join node is replaced by an
    edge to a ContinueLoop node that references the Loop node object.

    Each node in a loop will have an attribute 'loops', which is a
    set of all the Loop objects it belongs to.
    """

    def flatten_block(self, keep_all_cobol_stmts=False):
        """Translate the graph structure to a Block of CobolStatement or
        structure elements and return it.
        """
        scope = RootReductionScope(self.graph, keep_all_cobol_stmts)
        redux = BlockReduction(self.graph, scope, start_node=Entry)
        redux.resolve_tail_nodes()
        return redux.block


    @classmethod
    def from_branch_graph(cls, branch_graph):
        """Identify loops in a BranchJoinGraph and break them by adding Loop
        and ContinueLoop nodes.  Returns the resulting AcyclicBranchGraph.
        """
        dag = cls()

        # Copy by way of edges, to avoid getting copies of the node objects
        dag.graph.add_edges_from(branch_graph.graph.edges(keys=True, data=True))

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
        continue_loop = ContinueLoop(loop)
        self.graph.add_node(continue_loop, loop=loop, loops=[loop])

        for node in component:
            self._tag_node_in_loop(node, loop)

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


    def _tag_node_in_loop(self, node, loop):
        self.graph.node[node]['loop'] = loop

        node_loops = self.graph.node[node].get('loops')
        if node_loops is None:
            node_loops = self.graph.node[node]['loops'] = set()
        node_loops.add(loop)

