#!/usr/bin/env python3

import sys
from setuptools import setup

# From https://github.com/pypa/setuptools/blob/master/setup.py
needs_pytest = set(['ptr', 'pytest', 'test']).intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

setup(
    name = 'cobol-sharp',
    version = '0.1',
    license = 'GPLv3',
    description = 'Cobol code revisualiser',
    author = 'Peter Liljenberg',
    author_email = 'peter.liljenberg@gmail.com',
    keywords = 'cobol code analysis',
    url = 'https://github.com/petli/cobol-sharp',

    scripts = [ 'src/tools/cobolsharp',
                ],

    package_dir = { '': 'src' },
    packages = [ 'CobolSharp' ],

    package_data = {
        'CobolSharp': [
            'data/koopa-*.jar',
        ],
    },
    include_package_data = True,
    zip_safe = False,

    # The JAR must be unpacked
    eager_resources = [
        'data/'
    ],

    install_requires = [
        'networkx ~= 1.11',
        'pygraphviz ~= 1.3',
    ],

    tests_require = [
        'pytest ~= 3.0.3'
    ],

    setup_requires = [
        "setuptools_git",
    ] + pytest_runner,
)
