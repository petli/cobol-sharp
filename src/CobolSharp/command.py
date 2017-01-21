# Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
# Licensed under GPLv3, see file LICENSE in the top directory

from CobolSharp import *
from CobolSharp.structure import Method
from CobolSharp.syntax import PerformSectionStatement

import sys
import os
import argparse
import networkx as nx

OUTPUT_FORMATS = [
    'xml',
    'full_stmt_graph',
    'stmt_graph',
    'cobol_graph',
    'acyclic_graph',
    'scope_graph',
    'code',
    'html'
    ]

LANGUAGES = {
    'py': Pythonish,
    'python': Pythonish,
    'cs': CSharpish,
    'C#': CSharpish,
}

def main():
    args = parser.parse_args()
    for source_path in args.sources:
        if args.destdir:
            output_base = os.path.join(args.destdir, os.path.basename(source_path))
        else:
            output_base = source_path

        output_base = os.path.splitext(output_base)[0]

        source_file = open(source_path, 'rt', encoding=args.encoding, newline='')

        if args.format == 'xml':
            xml_path = '{}.xml'.format(output_base)
            run_koopa(source_file, xml_path, tabsize=args.tabsize)
            print('wrote', xml_path)
        else:
            program = parse(source_file, tabsize=args.tabsize)
            process_program(args, output_base, program)


def process_program(args, output_base, program):
    language = LANGUAGES[args.language]

    if args.format == 'code':
        path = '{}.{}'.format(output_base, language.file_suffix)
        outputter = TextOutputter(open(path, 'wt', encoding='utf-8'), language)
    elif args.format == 'html':
        path = '{}.html'.format(output_base)
        outputter = HtmlOutputter(program, open(path, 'wt', encoding='utf-8'), language)
    else:
        path = None
        outputter = None

    if outputter:
        formatter = CodeFormatter(outputter, language)
    else:
        formatter = None

    # Map sections to their reachable statment graphs
    section_stmt_graphs = {}
    section_scope_graphs = {}

    for section in program.proc_div.sections.values():
        # Only process selected graph if outputting graphs, otherwise
        # all are needed to output code in some form
        if not (not args.section
                or args.section == section.name
                or outputter is not None):
            continue

        if not args.section or args.section == section.name:
            graph_path = '{}_{}.dot'.format(output_base, section.name)
        else:
            graph_path = None

        full_graph = StmtGraph.from_section(section)

        if args.format == 'full_stmt_graph':
            if graph_path:
                nx.nx_pydot.write_dot(full_graph.graph, graph_path)
                print('wrote', graph_path)
            continue

        reachable = full_graph.reachable_subgraph()
        section_stmt_graphs[section] = reachable

        if args.format == 'stmt_graph':
            if graph_path:
                nx.nx_pydot.write_dot(reachable.graph, graph_path)
                print('wrote', graph_path)
            continue

        cobol_graph = CobolStructureGraph.from_stmt_graph(reachable)

        if args.format == 'cobol_graph':
            if graph_path:
                cobol_graph.write_dot(graph_path)
                print('wrote', graph_path)
            continue

        dag = AcyclicStructureGraph.from_cobol_graph(cobol_graph)

        if args.format == 'acyclic_graph':
            if graph_path:
                dag.write_dot(graph_path)
                print('wrote', graph_path)
            continue

        scope_graph = ScopeStructuredGraph.from_acyclic_graph(dag, debug=args.debug)
        section_scope_graphs[section] = scope_graph

        if args.format == 'scope_graph':
            if graph_path:
                scope_graph.write_dot(graph_path)
                print('wrote', graph_path)
            continue

    if not outputter:
        return

    if args.unused:
        # Include all sections in output
        used_sections = set(program.proc_div.sections.values())
    else:
        # Find the sections that can be reached from the first section
        used_sections = set()

        if args.section:
            first_section = program.proc_div.sections.get(args.section)
            if first_section is None:
                sys.exit('{}: section not defined: {}'.format(program.path, args.section))
        else:
            first_section = program.proc_div.first_section

        queue = [first_section]
        used_sections.add(first_section)
        while queue:
            section = queue.pop()
            for node in section_stmt_graphs[section].graph:
                if (isinstance(node, PerformSectionStatement)
                    and node.section is not None
                    and node.section not in used_sections):
                    used_sections.add(node.section)
                    queue.append(node.section)

    for section in program.proc_div.sections_in_order():
        if section in used_sections:
            block = section_scope_graphs[section].flatten_block()
            formatter.format_method(Method(section, block))
        else:
            print('unused section', section.name)

    outputter.close()
    print('wrote', path)

#
# Set up the command argument parsing
#

parser = argparse.ArgumentParser(description='Cobol revisualiser')
parser.add_argument('sources', nargs='+', help='Cobol source files', metavar="COBOL_FILE")
parser.add_argument('-s', '--section',
                    help='override start section, or only output graph for this one')
parser.add_argument('-f', '--format', choices=OUTPUT_FORMATS, default='html',
                    help='output format (default html)')
parser.add_argument('-l', '--language', choices=sorted(LANGUAGES.keys()), default='C#',
                    help='generated code language-ish (default C#)')
parser.add_argument('-t', '--tabsize', type=int, default=4,
                    help='expand tabs by this many spaces (default 4)')
parser.add_argument('-e', '--encoding', default='iso-8859-1',
                    help='source file encoding (default iso-8859-1)')
parser.add_argument('-d', '--destdir',
                    help='write files to this directory instead of the source code dir')
parser.add_argument('-D', '--debug', action='store_true',
                    help='debug mode aiding in inspecting the analysis results')
parser.add_argument('-u', '--unused', action='store_true',
                    help='include sections not referenced from any reachable code')
