#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Erigones, s. r. o.
# All Rights Reserved
#
# This software is licensed as described in the README.rst and LICENSE
# files, which you should have received as part of this distribution.

import sys
import codecs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# noinspection PyPep8Naming
#from ludolph-hello-world.__init__ import __version__ as VERSION
VERSION = '1.0'

DESCRIPTION = 'Hello world plugin'

with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

if sys.version_info[0] < 3:
    DEPS = ['ludolph', 'dnspython']
else:
    DEPS = ['ludolph', 'dnspython3']

CLASSIFIERS = [
    'Environment :: Console',
    'Environment :: Plugins',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: MIT License',
    'Operating System :: MacOS',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

packages = [
    'hello_world',
]

setup(
    name='ludolph-hello-world',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author='Erigones',
    author_email='erigones [at] erigones.com',
    url='https://github.com/erigones/ludolph-skeleton/',
    license='MIT',
    packages=packages,
    install_requires=DEPS,
    platforms='any',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
