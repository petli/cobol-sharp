# CobolSharp

This is a tool to extract code structure from COBOL written according
to mid-80's best practices and revisualize it as more modern code
structures.  The purpose is to make it easier to analyze legacy code
to understand what it does, extract the core business logic, and then
reimplement it in modern languages.

But it is not a tool to translate Cobol code fully into a modern
language, since it only considers the code, not the data.  Even though
the output code might look like it could be run if the tool could just
translate the expressions and data structures too, the result would
just be COBOL code in fancy dress.  The COBOL data model is so far
removed from what you'd use in C# or Python that the translated code
would not be much less messy to maintain than the original code.

(Despite the harsh tone in the previous paragraph, pull requests to
translate expression and data structures too will be accepted!)


## Background

In COBOL-74 an `if` block was best limited to a few simple
statements, avoiding any nested `if` since that would likely end up
associating an `else` block with the wrong `if`.  There where no
syntax for loops except for performing another section or paragraph
repeatedly.  On top of this the layout of each code line had
restrictions that discouraged or even disallowed using indentation
to indicate code structure.

As a result, what is today implemented with nested, indented code
blocks was implemented with gotos, typically enforcing a paragraph
naming scheme to help get some idea of the code structure.

COBOL-85 added proper code scope terminators (i.e.  `if ... end-if.`,
the switch statement `evaluate` and inline `perform` loops, but much
code continued to be written in mostly a COBOL-74 way.


# Installation

CobolSharp requires Python 3 and a Java runtime installed in `$PATH`.
Graphviz is needed to plot code graphs, but not for generating code.
It works both on Unix-like systems and Windows.

CobolSharp can be installed systemwide with from PyPi:

    pip3 install cobolsharp

Or for your own user, to avoid requiring root:

    pip3 install --user cobolsharp

An executable script (or binary on Windows) called `cobolsharp` is
installed.  If you install with `--user` it may not be in `$PATH`, but in
`~/.local/bin/cobolsharp`.

## From code

You can also clone the repository at
https://github.com/petli/cobol-sharp and install from the code:

    python3 setup.py install

For development setup it is recommended to use a `virtualenv`, e.g.:

    virtualenv --python=python3 ~/test/cobolsharp
    ~/test/cobolsharp/bin/python setup.py develop

## Unit tests

There's a small test suite:

    python3 setup.py test


# Usage

Run `cobolsharp --help` to see detailed help on all command line
flags.

CobolSharp can produce a number of output formats, chosen with the
`-f` flag:

* `html`: COBOL code and translated code in a web page (default
  format)

* `code`: translated code written to a source file

* `full_stmt_graph`: A graph of all COBOL statements

* `stmt_graph`: A graph of all reachable COBOL statements

* `cobol_graph`: Cobol code structure graph

* `acyclic_graph`: Code structure graph with loops identified and
  broken up

* `scope_graph`: Code scope graph where each loop scope and exit nodes
  have been identified

* `xml`: Koopa XML parse tree, mainly useful during CobolSharp
  development


## Cross-referencing code

The `html` format (the default) creates a standalone web page with
both the original COBOL code and the translated code side-by-side.

Clicking a line in either of the code columns will scroll to and
highlight the corresponding line in the other one (if there is one).

Larger code blocks (currently five lines or more) in the translated
source can be folded and unfolded.  There's a set of buttons to
fold/unfold everything or all function levels.

Functions and goto labels in the translated source 

The indentation level in the translated code is colour-coded, and the
corresponding line in the COBOL code has the same colour.  This can be
turned off with checkboxes.

Line numbers and navigation buttons can be turned off to make it easy
to cut-and-paste code from the page into a separate file.


## Plotting graphs

The graph formats produce `.dot` files.  They can be plotted into PNGs
(and many other formats) with graphviz, e.g.:

    dot -Tpng -O *.dot


## Limitations

This tool will only work well for code that follows best practices on
writing structured COBOL.  Mainly:

* `perform` is only used to pass control to a single section, not a
  suite of them or of individual paragraphs.  I.e. a section
  behaves as function.

* There are no cross-section `go to` jumps.

In addition the tool only understands the COBOL supported by the Koopa
parser, and may not handle all statements correctly even if they are
parsed well.  See the project issue list for current outstanding issues.


# Translation process

The COBOL code is parsed by Koopa into an XML parse tree, which is
translated into a graph of statements.  This is refined in several
steps to identify structured code.  For details on this, see the
documentation strings and comments in `CobolSharp/graph.py`.

The final graph is then flattened into linear code.  Several
strategies are used to decide which representation to use, a trade-off
between avoiding code jumps but also not producing very deeply nested
code.  For details on these strategies see the code comments in
`CobolSharp/analyze.py`.  The weightings used in these decisions can
no doubt be tuned to produce better output, and any improvements on
them are most welcome.

The code is flattened for a local optimization, without attempting to
find the optimal representation for a larger section of the code
graph.  This can also be an area for improvements.

## But the translated code still contains gotos!

Yes, it often will.  There are pathological cases which cannot be
resolved in a structured way (see e.g. `test/crossedbranches.cbl`).
The trade-off mentioned above will also keep some gotos in more
complex code, and maybe even add labels that aren't in the original
COBOL code.  This is another reason why this is mainly a tool to
better understand COBOL code, not a tool to translate it fully.


# License

Copyright (C) 2017 Peter Liljenberg <peter.liljenberg@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

## Koopa

The Koopa parser generator is distributed under a BSD license.  See
http://koopa.sourceforge.net/ for more information.
