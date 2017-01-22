#!/usr/bin/env python3

import sys
from setuptools import setup

# From https://github.com/pypa/setuptools/blob/master/setup.py
needs_pytest = set(['ptr', 'pytest', 'test']).intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

setup(
    name = 'cobolsharp',
    version = '0.1',
    license = 'GPLv3',
    description = 'COBOL code revisualizer',
    author = 'Peter Liljenberg',
    author_email = 'peter.liljenberg@gmail.com',
    keywords = 'cobol code analysis',
    url = 'https://github.com/petli/cobol-sharp',

    # Not sure exact minimum Python3 version, but this is probably
    # a fairly good stab
    python_requires = '~= 3.3',

    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Topic :: Software Development',
        'Programming Language :: Python :: 3 :: Only',
    ],

    entry_points = {
        'console_scripts': [
            'cobolsharp = CobolSharp.command:main',
        ],
    },

    package_dir = { '': 'src' },
    packages = [ 'CobolSharp' ],

    package_data = {
        'CobolSharp': [
            'data/koopa-*.jar',
            'templates/*.html',
            'templates/*.css',
            'templates/*.js',
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
        'pydotplus ~= 2.0',
        'Jinja2 ~= 2.8',
    ],

    tests_require = [
        'pytest ~= 3.0.3'
    ],

    setup_requires = [
        "setuptools_git",
    ] + pytest_runner,
)
