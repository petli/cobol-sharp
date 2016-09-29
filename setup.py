#!/usr/bin/env python3

from setuptools import setup

setup(
    name = 'cobol-sharp',
    version = '0.1',
#    license = 'MIT',
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

    # The JAR must be unpacked
    eager_resources = [
        'data/'
    ],

    setup_requires = [
        "setuptools_git",
    ],
)
