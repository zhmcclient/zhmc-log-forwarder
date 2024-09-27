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

Troubleshooting
===============

This section describes some issues and how to resolve them. If you encounter
an issue that is not covered here, see :ref:`Reporting issues`.

The `zhmcclient Troubleshooting <https://python-zhmcclient.readthedocs.io/en/latest/appendix.html#troubleshooting>`_
section also applies to the log forwarder.

Permission error with log forwarder config file
-----------------------------------------------

Example:

.. code-block:: bash

  $ zhmc_log_forwarder -c config.yaml
  Error: Permission error reading log forwarder config file ...

You don't have permission to read from the log forwarder config file. Change the
permissions with ``chmod``, check ``man chmod`` if you are unfamiliar with it.

YAML syntax error in log forwarder config file
----------------------------------------------

Example:

.. code-block:: bash

    $ zhmc_log_forwarder -c config.yaml
    Error: YAML error reading log forwarder config file ...

The log forwarder config file breaks the syntax rules of the YAML specification.

Compare your log forwarder config file with the sample log forwarder config file
shown with ``zhmc_log_forwarder --help-config-file``.

You can also check the `YAML specification`_.

.. _YAML specification: http://yaml.org/spec/1.2/spec.html

YAML validation error in log forwarder config file
--------------------------------------------------

Example:

.. code-block:: bash

    $ zhmc_log_forwarder -c config.yaml
    Error: Validation of log forwarder config file ... failed on ...

There are additional elements in the log forwarder config file, or required elements
are missing, or other validation rules are violated.

Compare your log forwarder config file with the sample log forwarder config file
shown with ``zhmc_log_forwarder --help-config-file``.
