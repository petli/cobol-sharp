# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from CobolSharp import *
from CobolSharp.structure import Method

import sys
import os
import argparse
import networkx as nx

OUTPUT_FORMATS = [
    'full_stmt_graph',
    'stmt_graph',
    'cobol_graph',
    'acyclic_graph',
    'scope_graph',
    'code',
    'html'
    ]

def main():
    args = parser.parse_args()
    for source_path in args.sources:
        program = parse(open(source_path, 'rt', encoding=args.encoding, newline=''), tabsize=args.tabsize)

        if args.destdir:
            output_base = os.path.join(args.destdir, os.path.basename(source_path))
        else:
            output_base = source_path

        output_base = os.path.splitext(output_base)[0]

        process_program(args, output_base, program)


def process_program(args, output_base, program):
    if args.format == 'code':
        path = '{}.py'.format(output_base)
        outputter = TextOutputter(open(path, 'wt', encoding='utf-8'))
    elif args.format == 'html':
        path = '{}.html'.format(output_base)
        outputter = HtmlOutputter(program, open(path, 'wt', encoding='utf-8'))
    else:
        path = None
        outputter = None

    if outputter:
        formatter = PythonishFormatter(outputter)
    else:
        formatter = None

    for section in program.proc_div.sections_in_order():
        full_graph = StmtGraph.from_section(section)
        graph_path = '{}_{}.dot'.format(output_base, section.name)

        if args.format == 'full_stmt_graph':
            nx.nx_pydot.write_dot(full_graph.graph, graph_path)
            print('wrote', graph_path)
            continue

        reachable = full_graph.reachable_subgraph()

        if args.format == 'stmt_graph':
            nx.nx_pydot.write_dot(reachable.graph, graph_path)
            print('wrote', graph_path)
            continue

        cobol_graph = CobolStructureGraph.from_stmt_graph(reachable)

        if args.format == 'cobol_graph':
            cobol_graph.write_dot(graph_path)
            print('wrote', graph_path)
            continue

        dag = AcyclicStructureGraph.from_cobol_graph(cobol_graph)

        if args.format == 'acyclic_graph':
            dag.write_dot(graph_path)
            print('wrote', graph_path)
            continue

        scope_graph = ScopeStructuredGraph.from_acyclic_graph(dag)

        if args.format == 'scope_graph':
            scope_graph.write_dot(graph_path)
            print('wrote', graph_path)
            continue

        block = scope_graph.flatten_block()
        formatter.format_method(Method(section, block))

    if outputter:
        outputter.close()
        print('wrote', path)

#
# Set up the command argument parsing
#

parser = argparse.ArgumentParser(description='Cobol revisualiser')
parser.add_argument('sources', nargs='+', help='Cobol source files', metavar="COBOL_FILE")
parser.add_argument('-f', '--format', choices=OUTPUT_FORMATS, default='html',
                    help='output format (default html)')
parser.add_argument('-t', '--tabsize', type=int, default=4,
                    help='expand tabs by this many spaces (default 4)')
parser.add_argument('-e', '--encoding', default='iso-8859-1',
                    help='source file encoding (default iso-8859-1)')
parser.add_argument('-d', '--destdir',
                    help='write files to this directory instead of the source code dir')

