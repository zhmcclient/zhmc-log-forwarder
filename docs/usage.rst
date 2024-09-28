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


Usage
=====

This section describes how to use the log forwarder beyond the quick introduction
in :ref:`Quickstart`.


Running on a system
-------------------

If you want to run the log forwarder on some system (e.g. on your workstation for
trying it out), it is recommended to use a virtual Python environment.

With the virtual Python environment active, follow the steps in
:ref:`Quickstart` to install, establish the required files, and to run the
log forwarder.


Running in a Docker container
-----------------------------

If you want to run the log forwarder in a Docker container you can create the
container as follows, using the Dockerfile provided in the Git repository.

* Clone the Git repository of the log forwarder and switch to the clone's root
  directory:

  .. code-block:: bash

      $ git clone https://github.com/zhmcclient/zhmc-log-forwarder
      $ cd zhmc-log-forwarder

* Build a local Docker image as follows:

  .. code-block:: bash

      $ make docker

  This builds a container image named 'zhmc_log_forwarder:latest' in your local
  Docker environment.

  The log forwarder config file is not included in the image, and needs to be
  provided when running the image.

* Run the local Docker image as follows:

  .. code-block:: bash

      $ docker run --rm -v $(pwd)/myconfig:/root/myconfig zhmc_log_forwarder -c /root/myconfig/config.yaml -v

  In this command, the log forwarder config file is provided on the local system
  as ``./myconfig/config.yaml``. The ``-v`` option of 'docker run' mounts the
  ``./myconfig`` directory to ``/root/myconfig`` in the container's file system.
  The ``-c`` option of the log forwarder references the config file as it
  appears in the container's file system.


Setting up the HMC
------------------

Usage of this package requires that the HMC in question is prepared
accordingly:

* The Web Services API must be enabled on the HMC.

  You can do that in the HMC GUI by selecting "HMC Management" in the left pane,
  then opening the "Configure API Settings" icon on the pain pane,
  then selecting the "Web Services" tab on the page that comes up, and
  finally enabling the Web Services API on that page.

  The above is on a z16 HMC, it may be different on older HMCs.

  If you cannot find this icon, then your userid does not have permission
  for the respective task on the HMC. In that case, there should be some
  other HMC admin you can go to to get the Web Services API enabled.

* The HMC should be configured with a CA-verifiable server certificate.
  See :ref:`HMC certificate` for details.


Setting up firewalls or proxies
-------------------------------

If you have to configure firewalls or proxies between the system where you
run the ``zhmc_log_forwarder`` command and the HMC, the following ports
need to be opened:

* 6794 (TCP) - for the HMC API HTTP server
* 61612 (TCP) - for the HMC API message broker via JMS over STOMP

For details, see sections "Connecting to the API HTTP server" and
"Connecting to the API message broker" in the :term:`HMC API` book.


HMC userid requirements
-----------------------

This section describes the requirements on the HMC userid that is used by
the ``zhmc_log_forwarder`` command.

To return all metrics supported by the command, the HMC userid must have the
following permissions:

* The HMC userid must have the following flag enabled:

  - "Allow access to Web Services management interfaces" flag of the user in
    the HMC GUI, or "allow-management-interfaces" property of the user at the
    WS-API.

* Task permission for the "Audit and Log Management" task.

  This is required to forward audit logs.

* Task permission for the "View Security Logs" task.

  This is required to forward security logs.


HMC certificate
---------------

By default, the HMC is configured with a self-signed certificate. That is the
X.509 certificate presented by the HMC as the server certificate during SSL/TLS
handshake at its Web Services API.

The HMC should be configured to use a CA-verifiable certificate. This can be
done in the HMC task "Certificate Management". See also the :term:`HMC Security`
book and Chapter 3 "Invoking API operations" in the :term:`HMC API` book.

The 'zhmc_log_forwarder' command provides control knobs for the verification of
the HMC certificate via the ``hmc_verify_cert`` parameter in the
:ref:`log forwarder config file`, as follows:

* Not specified or specified as ``true`` (default): Verify the HMC certificate
  using the CA certificates from the first of these locations:

  - The certificate file or directory in the ``REQUESTS_CA_BUNDLE`` environment
    variable, if set
  - The certificate file or directory in the ``CURL_CA_BUNDLE`` environment
    variable, if set
  - The `Python 'certifi' package <https://pypi.org/project/certifi/>`_
    (which contains the
    `Mozilla Included CA Certificate List <https://wiki.mozilla.org/CA/Included_Certificates>`_).

* Specified with a string value: An absolute path or a path relative to the
  directory of the log forwarder config file. Verify the HMC certificate using the CA
  certificates in the specified certificate file or directory.

* Specified as ``false``: Do not verify the HMC certificate.
  Not verifying the HMC certificate means that hostname mismatches, expired
  certificates, revoked certificates, or otherwise invalid certificates will not
  be detected. Since this mode makes the connection vulnerable to
  man-in-the-middle attacks, it is insecure and should not be used in production
  environments.

If a certificate file is specified (using any of the ways listed above), that
file must be in PEM format and must contain all CA certificates that are
supposed to be used. Usually they are in the order from leaf to root, but
that is not a hard requirement. The single certificates are concatenated
in the file.

If a certificate directory is specified (using any of the ways listed above),
it must contain PEM files with all CA certificates that are supposed to be used,
and copies of the PEM files or symbolic links to them in the hashed format
created by the OpenSSL command ``c_rehash``.

An X.509 certificate in PEM format is base64-encoded, begins with the line
``-----BEGIN CERTIFICATE-----``, and ends with the line
``-----END CERTIFICATE-----``.
More information about the PEM format is for example on this
`www.ssl.com page <https://www.ssl.com/guide/pem-der-crt-and-cer-x-509-encodings-and-conversions>`_
or in this `serverfault.com answer <https://serverfault.com/a/9717/330351>`_.

Note that setting the ``REQUESTS_CA_BUNDLE`` or ``CURL_CA_BUNDLE`` environment
variables influences other programs that use these variables, too.

If you do not know which CA certificate the HMC has been configured with,
you can use the following OpenSSL commands to display the certificates
returned by the HMC. Look at the Issuer of the highest certificate in the CA
chain (usually the last one displayed):

.. code-block:: sh

    $ echo | openssl s_client -showcerts -connect $hmc_ip:6794 2>/dev/null | sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p' >/tmp/get-server-certs.pem
    $ openssl storeutl -noout -text -certs /tmp/get-server-certs.pem | grep -E "Certificate|Subject:|Issuer"

For more information, see the
`Security <https://python-zhmcclient.readthedocs.io/en/latest/security.html>`_
section in the documentation of the 'zhmcclient' package.


zhmc_log_forwarder command
--------------------------

The ``zhmc_log_forwarder`` command supports the following arguments:

.. When updating the command help, use a 100 char wide terminal
.. code-block:: text

    usage: zhmc_log_forwarder [options]

    A log forwarder for the IBM Z HMC. The log entries can be selected based on HMC log type (e.g.
    Security log, Audit log) and based on the point in time since when past log entries should be
    forwarded. It is possible to wait in a loop for future log entries to be created.Destinations can
    be standard output, standard error, or a syslog server. Multiple destinations are supported in
    parallel, e.g. the HMC Audit log can be sent to a QRadar syslog server, and both the HMC Audit log
    and Security log can be sent to a logDNA syslog server.

    General options:

      -h, --help            Show this help message and exit.

      --help-config-file    Show help about the config file format and exit.

      --help-log-message-file
                            Show help about the HMC log message file format and exit.

      --help-format         Show help about the output formats and exit.

      --help-format-line    Show help about the 'line' output format and exit.

      --help-format-cadf    Show help about the 'cadf' output format and exit.

      --help-time-format    Show help about the time field formatting and exit.

      --version             Show the version number of this program and exit.

      --debug               Show debug self-logged messages (if any).

    Config options:

      -c CONFIGFILE, --config-file CONFIGFILE
                            File path of the config file to use.


Log forwarder config file
-------------------------

The *log forwarder config file* tells the log forwarder which HMC to talk to for
obtaining metrics, and which userid and password to use for logging on to
the HMC.

It also specifies which logs to forward and to which destinations the log
forwarder should forward the logs.

The log forwarder config file is in YAML format. Here is an example:

.. code-block:: yaml

    # HMC connection data (see below for details)
    hmc_host: 10.11.12.13
    hmc_user: myuser
    hmc_password: mypassword
    hmc_verify_cert: mycerts/ca.pem
    stomp_retry_timeout_config:
      connect_timeout: null
      connect_retries: null
      reconnect_sleep_initial: null
      reconnect_sleep_increase: null
      reconnect_sleep_max: null
      reconnect_sleep_jitter: null
      keepalive: null
      heartbeat_send_cycle: null
      heartbeat_receive_cycle: null
      heartbeat_receive_check: null

    # Label for the HMC to be used in the log message (as field 'label').
    label: myregion-myzone-myhmc

    # Point in time since when past log entries are included:
    # - 'now': Include past log entries since now. This may actually include log
    #   entries from the recent past.
    # - 'all': Include all available past log entries.
    # - A date and time string suitable for Python dateutil.parser. Timezones in
    #   the string are ignored and the local timezone is used instead.
    since: now

    # Wait for future log entries.
    future: true

    # Logging configuration for the operations of the log forwarder (see below for details)
    selflog_dest: stdout
    selflog_format: '%(levelname)s: %(message)s'
    selflog_time_format: '%Y-%m-%d %H:%M:%S.%f%z'

    # File path of HMC log message file (in YAML format) to be used with the
    # cadf output format. Relative file paths are relative to the directory
    # containing this config file. Default is null, which causes the file
    # provided with the zhmc_log_forwarder package to be used.
    log_message_file: null

    # Check data to be included in the generated CADF log records.
    check_data:

      # Subnet of the IMGMT network of the pod, in CIDR notation
      imgmt_subnet: 172.16.192.0/24

      # List of functional users of the pod
      functional_users:
        - zaasmoni
        - zaasauto

    # List of log forwardings. A log forwarding mainly defines a set of logs to
    # collect, and a destination to forward them to.
    forwardings:

      -
        # Name of the forwarding (unique within configuration).
        name: Example forwarding

        # List of HMC logs to include:
        # - 'security': HMC Security Log.
        # - 'audit': HMC Audit Log.
        logs: [security, audit]

        # Destination:
        # - 'stdout': Standard output.
        # - 'stderr': Standard error.
        # - 'syslog': Local or remote system log.
        dest: stdout

        # IP address or hostname of the syslog server (for syslog destinations).
        syslog_host: 10.11.12.14

        # Port number of the syslog server (for syslog destinations).
        syslog_port: 514

        # Port type of the syslog server (for syslog destinations).
        syslog_porttype: udp

        # Syslog facility name (for syslog destinations).
        syslog_facility: user

        # Output format of the log records written to the destination:
        # - 'line': Single line formatted using the line_format config parameter
        # - 'cadf': CADF format as a JSON string
        format: line

        # Format for 'line' and 'cadf' output formats (for details, see below)
        line_format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'

        # Format for the 'time' field in the log message, as a Python
        # datetime.strftime() format string, or one of: 'iso8601', 'iso8601b',
        # or 'syslog'.
        # Invoke with --help-time-format for details.
        # Typical setting for 'line' format:
        time_format: 'iso8601'
        # Typical setting for 'cadf' format:
        # time_format: 'syslog'

Where:

* ``hmc_host`` - DNS host name or IP address of the HMC.

* ``hmc_user`` - Userid on the HMC to be used for logging on.

* ``hmc_password`` - Password of that HMC userid.

* ``hmc_verify_cert`` - Controls whether and how the HMC server certificate is
  verified:

  - ``true`` (default): CA certificates in the Python 'certifi' package
  - ``false``: Disable CA certificate validation
  - string: Path to CA PEM file or CA directory (with c_rehash links)

  For more details, see :ref:`HMC certificate`.

* ``stomp_retry_timeout_config`` - STOMP retry/timeout configuration.
  ``null`` means to use the zhmcclient defaults. For a description, see
  https://python-zhmcclient.readthedocs.io/en/latest/notifications.html#zhmcclient.StompRetryTimeoutConfig

* ``selflog_dest`` - Destination for any self-log entries:

  - ``stdout``: Standard output
  - ``stderr``: Standard error

* ``selflog_format`` - Format of any self-log entries, as a format string for
  Python `log record attributes <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_

* ``selflog_time_format`` - Format for the 'asctime' field of any self-log
  entries, using Python
  `strftime format codes <https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes>`_.

  Example::

      selflog_time_format: '%Y-%m-%d %H:%M:%S.%f%z'

* ``formatting[].line_format`` - Format for 'line' and 'cadf' output formats,
  as a Python new-style format string. Invoke with ``--help-format-line`` or
  ``--help-format-cadf`` for details.

  Example for 'line' format::

      line_format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'

  Example for 'cadf' format::

      line_format: '{time} {label} {cadf}'


Self-logging
------------

The log forwarder supports logging its own activities. That self-logging is
always enabled and the log destination and format can be controlled with the
``selflog_...`` parameters in the log forwarder config file.
