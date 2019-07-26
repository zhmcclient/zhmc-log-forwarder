.. Copyright 2016-2017 IBM Corp. All Rights Reserved.
..
.. Licensed under the Apache License, Version 2.0 (the "License");
.. you may not use this file except in compliance with the License.
.. You may obtain a copy of the License at
..
..    http://www.apache.org/licenses/LICENSE-2.0
..
.. Unless required by applicable law or agreed to in writing, software
.. distributed under the License is distributed on an "AS IS" BASIS,
.. WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
.. See the License for the specific language governing permissions and
.. limitations under the License.
..

zhmc_qradar - QRadar support for the IBM Z HMC, written in pure Python
======================================================================

.. image:: https://img.shields.io/pypi/v/zhmc_qradar.svg
    :target: https://pypi.python.org/pypi/zhmc_qradar/
    :alt: Version on Pypi

.. .. image:: https://travis-ci.org/zhmcclient/zhmc-qradar.svg?branch=master
..     :target: https://travis-ci.org/zhmcclient/zhmc-qradar
..     :alt: Travis test status (master)

.. .. image:: https://ci.appveyor.com/api/projects/status/i022iaeu3dao8j5x/branch/master?svg=true
..     :target: https://ci.appveyor.com/project/leopoldjuergen/zhmc-qradar
..     :alt: Appveyor test status (master)

.. .. image:: https://readthedocs.org/projects/zhmc-qradar/badge/?version=latest
..     :target: http://zhmc-qradar.readthedocs.io/en/latest/
..     :alt: Docs build status (latest)

.. .. image:: https://img.shields.io/coveralls/zhmcclient/zhmc-qradar.svg
..     :target: https://coveralls.io/r/zhmcclient/zhmc-qradar
..     :alt: Test coverage (master)

.. .. image:: https://codeclimate.com/github/zhmcclient/zhmc-qradar/badges/gpa.svg
..     :target: https://codeclimate.com/github/zhmcclient/zhmc-qradar
..     :alt: Code Climate

.. contents:: Contents:
   :local:

Overview
========

The zhmc_qradar package provides QRadar support for the IBM Z HMC, written in
pure Python.

It provides a zhmc_qradar program that runs as a kind of bridge between the
HMC and a QRadar services, and forwards the Security Log and the Audit Log
of the HMC to the QRadar service.

Installation
============

The quick way:

.. code-block:: bash

    $ pip install zhmc_qradar

.. For more details, see the `Installation section`_ in the documentation.

.. _Installation section: http://zhmc-qradar.readthedocs.io/en/stable/intro.html#installation

Quickstart
===========

1. Create a zhmc_qradar config file, that specifies the targeted HMC and desired
   destination for the logs.

   **TBD: Provide an example config file.**

2. Start the script as a job (it runs forever):

.. code-block:: text

    zhmc_qradar -c config_file

Documentation
=============

The zhmc_qradar documentation is on RTD:

* `Documentation for latest version on Pypi`_
* `Documentation for master branch in Git repo`_

.. _Documentation for latest version on Pypi: http://zhmc-qradar.readthedocs.io/en/stable/
.. _Documentation for master branch in Git repo: http://zhmc-qradar.readthedocs.io/en/latest/

Contributing
============

For information on how to contribute to this project, see the
`Development section`_ in the documentation.

.. _Development section: http://zhmc-qradar.readthedocs.io/en/stable/development.html

License
=======

The zhmc_qradar package is licensed under the `Apache 2.0 License`_.

.. _Apache 2.0 License: https://github.com/zhmcclient/zhmc-qradar/tree/master/LICENSE
