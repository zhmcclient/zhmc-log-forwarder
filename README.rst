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

zhmc-log-forwarder - A log forwarder for the IBM Z HMC, written in pure Python
==============================================================================

.. image:: https://img.shields.io/pypi/v/zhmc_log_forwarder.svg
    :target: https://pypi.python.org/pypi/zhmc_log_forwarder/
    :alt: Version on Pypi

.. .. image:: https://travis-ci.org/zhmcclient/zhmc-log-forwarder.svg?branch=master
..     :target: https://travis-ci.org/zhmcclient/zhmc-log-forwarder
..     :alt: Travis test status (master)

.. .. image:: https://ci.appveyor.com/api/projects/status/i022iaeu3dao8j5x/branch/master?svg=true
..     :target: https://ci.appveyor.com/project/leopoldjuergen/zhmc-log-forwarder
..     :alt: Appveyor test status (master)

.. .. image:: https://readthedocs.org/projects/zhmc-log-forwarder/badge/?version=latest
..     :target: http://zhmc-log-forwarder.readthedocs.io/en/latest/
..     :alt: Docs build status (latest)

.. .. image:: https://img.shields.io/coveralls/zhmcclient/zhmc-log-forwarder.svg
..     :target: https://coveralls.io/r/zhmcclient/zhmc-log-forwarder
..     :alt: Test coverage (master)

.. .. image:: https://codeclimate.com/github/zhmcclient/zhmc-log-forwarder/badges/gpa.svg
..     :target: https://codeclimate.com/github/zhmcclient/zhmc-log-forwarder
..     :alt: Code Climate

.. contents:: Contents:
   :local:

Overview
========

The zhmc-log-forwarder package provides a log forwarder for the IBM Z HMC,
written in pure Python.

It contains a command named ``zhmc_log_forwarder`` that collects security logs
and audit logs from the Z HMC and forwards the log entries to various
destinations, such as a QRadar service or the local syslog.

Installation
============

The quick way:

.. code-block:: bash

    $ pip install zhmc-log-forwarder

.. For more details, see the `Installation section`_ in the documentation.

.. _Installation section: http://zhmc-log-forwarder.readthedocs.io/en/stable/intro.html#installation

Quickstart
===========

1. Create a zhmc_log_forwarder config file, that specifies the targeted HMC and desired
   destination for the logs.

   **TBD: Provide an example config file.**

2. Start the script as a job (it runs forever):

.. code-block:: text

    zhmc_log_forwarder -c config_file

Documentation
=============

The zhmc_log_forwarder documentation is on RTD:

* `Documentation for latest version on Pypi`_
* `Documentation for master branch in Git repo`_

.. _Documentation for latest version on Pypi: http://zhmc-log-forwarder.readthedocs.io/en/stable/
.. _Documentation for master branch in Git repo: http://zhmc-log-forwarder.readthedocs.io/en/latest/

Contributing
============

For information on how to contribute to this project, see the
`Development section`_ in the documentation.

.. _Development section: http://zhmc-log-forwarder.readthedocs.io/en/stable/development.html

License
=======

The zhmc_log_forwarder package is licensed under the `Apache 2.0 License`_.

.. _Apache 2.0 License: https://github.com/zhmcclient/zhmc-log-forwarder/tree/master/LICENSE
