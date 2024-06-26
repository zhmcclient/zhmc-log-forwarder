#!/usr/bin/env python
# Copyright 2019-2019 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Setup script for zhmc-log-forwarder project.
"""

import os
import re
import setuptools


def get_version(version_file):
    """
    Execute the specified version file and return the value of the __version__
    global variable that is set in the version file.

    Note: Make sure the version file does not depend on any packages in the
    requirements list of this package (otherwise it cannot be executed in
    a fresh Python environment).
    """
    # pylint: disable=unspecified-encoding
    with open(version_file, 'r') as fp:
        version_source = fp.read()
    _globals = {}
    exec(version_source, _globals)  # pylint: disable=exec-used
    return _globals['__version__']


def get_requirements(requirements_file):
    """
    Parse the specified requirements file and return a list of its non-empty,
    non-comment lines. The returned lines are without any trailing newline
    characters.
    """
    # pylint: disable=unspecified-encoding
    with open(requirements_file, 'r') as fp:
        lines = fp.readlines()
    reqs = []
    for line in lines:
        line = line.strip('\n')
        if not line.startswith('#') and line != '':
            reqs.append(line)
    return reqs


def read_file(a_file):
    """
    Read the specified file and return its content as one string.
    """
    # pylint: disable=unspecified-encoding
    with open(a_file, 'r') as fp:
        content = fp.read()
    return content


# pylint: disable=invalid-name
requirements = get_requirements('requirements.txt')
install_requires = [req for req in requirements
                    if req and not re.match(r'[^:]+://', req)]
dependency_links = [req for req in requirements
                    if req and re.match(r'[^:]+://', req)]
package_version = get_version(os.path.join('zhmc_log_forwarder', 'version.py'))

# Docs on setup():
# * https://docs.python.org/2.7/distutils/apiref.html?
#   highlight=setup#distutils.core.setup
# * https://setuptools.readthedocs.io/en/latest/setuptools.html#
#   new-and-changed-setup-keywords

setuptools.setup(
    name='zhmc-log-forwarder',
    version=package_version,
    packages=[
        'zhmc_log_forwarder',
    ],
    package_data={
        'zhmc_log_forwarder': [
            'zhmc_log_messages.yml',
        ],
    },
    entry_points=dict(
        console_scripts=[
            'zhmc_log_forwarder=zhmc_log_forwarder.zhmc_log_forwarder:main',
        ]
    ),
    install_requires=install_requires,
    dependency_links=dependency_links,
    description='A log forwarder for the IBM Z HMC',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    license='Apache License, Version 2.0',
    author='Andreas Maier',
    author_email='maiera@de.ibm.com',
    maintainer='Andreas Maier',
    maintainer_email='maiera@de.ibm.com',
    url='https://github.com/zhmcclient/zhmc-log-forwarder',
    project_urls={
        'Bug Tracker':
            'https://github.com/zhmcclient/zhmc-log-forwarder/issues',
        'Documentation': 'https://zhmc-log-forwarder.readthedocs.io/en/latest/',
        'Source Code': 'https://github.com/zhmcclient/zhmc-log-forwarder',
    },

    options={'bdist_wheel': {'universal': True}},
    zip_safe=True,  # This package can safely be installed from a zip file
    platforms='any',

    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration',
    ]
)
