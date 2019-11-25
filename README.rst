.. Copyright 2019-2019 IBM Corp. All Rights Reserved.
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

A log forwarder for the IBM Z HMC
=================================

.. .. image:: https://img.shields.io/pypi/v/zhmc-log-forwarder.svg
..    :target: https://pypi.python.org/pypi/zhmc-log-forwarder/
..    :alt: Version on Pypi

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
destinations, such as stdout, the local syslog, or a QRadar service.

The command can gather log entries from the past, since a specified date and
time, or since specific points such as now or all available entries.
The command can in addition subscribe for notifications from the HMC about new
log entries, so that it can wait for any future log entries to appear.

A short overview presentation is here: `IBM_Z_HMC_Log_Forwarder.pdf`_.

.. _IBM_Z_HMC_Log_Forwarder.pdf: IBM_Z_HMC_Log_Forwarder.pdf

Installation
============

Because the zhmc_log_forwarder package is not on Pypi yet, it needs to be
installed directly from its Git repo:

.. code-block:: text

    $ pip install git+https://github.ibm.com/zhmcclient/zhmc-log-forwarder.git@VERSION#egg=zhmc-log-forwarder

where ``VERSION`` needs to be replaced with the package version or branch name
you want to install. For example, to install the version from the ``master``
branch, issue:

.. code-block:: text

    $ pip install git+https://github.ibm.com/zhmcclient/zhmc-log-forwarder.git@master#egg=zhmc-log-forwarder

This will install the package and all of its prerequisite packages into your
current Python environment.

It is recommended to use a virtual Python environment, in order not to clutter
up your system Python.

..  $ pip install zhmc-log-forwarder

.. For more details, see the `Installation section`_ in the documentation.

.. .. _Installation section: http://zhmc-log-forwarder.readthedocs.io/en/stable/intro.html#installation

Quickstart
==========

1.  Make sure you installed the zhmc_log_forwarder package (see the previous
    section).

2.  Create a config file for the ``zhmc_log_forwarder`` command. The config
    file specifies the targeted HMC, the desired destination for the logs, and
    other data.

    An example config file with explanations of the parameters is shown when
    invoking:

    .. code-block:: text

        $ zhmc_log_forwarder --help-config-file

    Redirect that output into a file and edit that file as needed.

3.  Optional: The zhmc_log_forwarder package includes a default HMC log
    message file. That file is used when generating CADF output format and
    defines how the HMC log messages are classified in the CADF output.
    It is possible to specify your own HMC log message file using the
    ``log_message_file`` parameter in the config file. When omitting this
    parameter, or when setting it to ``null``, the default HMC log message
    file included with the zhmc_log_forwarder package is used.

    An example HMC log message file explaining its format is shown when
    invoking:

    .. code-block:: text

        $ zhmc_log_forwarder --help-log-message-file

4.  Start the ``zhmc_log_forwarder`` command as follows:

    .. code-block:: text

        $ zhmc_log_forwarder -c CONFIGFILE

    Where ``CONFIGFILE`` is the file path of the created config file.

    The command will run forever (or until stopped with Ctrl-C) and will
    forward the log records as specified in the config file.

Note that neither installation nor usage of the ``zhmc_log_forwarder`` command
requires cloning this Github repo or being in a specific directory.

.. Documentation
.. =============

.. The zhmc-log-forwarder documentation is on RTD:

.. * `Documentation for latest version on Pypi`_
.. * `Documentation for master branch in Git repo`_

.. .. _Documentation for latest version on Pypi: http://zhmc-log-forwarder.readthedocs.io/en/stable/
.. .. _Documentation for master branch in Git repo: http://zhmc-log-forwarder.readthedocs.io/en/latest/

.. Contributing
.. ============

.. For information on how to contribute to this project, see the
.. `Development section`_ in the documentation.

.. .. _Development section: http://zhmc-log-forwarder.readthedocs.io/en/stable/development.html

License
=======

The zhmc-log-forwarder package is licensed under the `Apache 2.0 License`_.

.. _Apache 2.0 License: https://github.com/zhmcclient/zhmc-log-forwarder/tree/master/LICENSE
