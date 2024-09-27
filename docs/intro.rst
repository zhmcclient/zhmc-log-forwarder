.. Copyright 2024 IBM Corp. All Rights Reserved.
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

Introduction
============

What this package provides
--------------------------

The zhmc-log-forwarder package provides a log forwarder for the
`IBM Z <https://www.ibm.com/it-infrastructure/z>`_ Hardware Management Console
(HMC), written in pure Python.

It contains a command named ``zhmc_log_forwarder`` that collects security
logs and audit logs from the :term:`Z HMC` and forwards the log entries to
various destinations, such as stdout, the local syslog, or a QRadar
service.

The command can gather log entries from the past, since a specified date
and time, or since specific points such as now or all available entries.
The command can in addition subscribe for notifications from the HMC
about new log entries, so that it can wait for any future log entries to
appear.

The log forwarder supports the following destinations:

- Standard output
- Standard error
- rsyslog server

and the following formats:

- Single line format
- :term:`Cloud Auditing Data Federation` (CADF) format, represented as a JSON
  string


Supported environments
----------------------

* Operating systems: Linux, macOS, Windows
* Python versions: 3.8 and higher
* HMC versions: 2.11.1 and higher

Quickstart
----------

* Install the log forwarder and all of its Python dependencies as follows:

  .. code-block:: bash

      $ pip install zhmc-log-forwarder

* Provide a *config file* for use by the log forwarder.

  The config file tells the log forwarder which HMC to talk to for
  obtaining the logs, and which userid and password to use for logging on to
  the HMC.

  It also defines which logs should be forwarded, and since when and whether
  the forwarder should remain running to wait for future log entries.

  Finally, it defines where the logs should be forwarded to. It supports
  multiple destinations at the same time.

  The following command displays help to create a config file, and shows an
  example config file:

  .. code-block:: bash

      $ zhmc_log_forwarder --help-config-file

  For details, see :ref:`Log forwarder config file`.

* Run the log forwarder as follows:

  .. code-block:: bash

      $ zhmc_log_forwarder -c config.yaml

Reporting issues
----------------

If you encounter a problem, please report it as an `issue on GitHub`_.

.. _issue on GitHub: https://github.com/zhmcclient/zhmc-log-forwarder/issues

License
-------

This package is licensed under the `Apache 2.0 License`_.

.. _Apache 2.0 License: http://apache.org/licenses/LICENSE-2.0
