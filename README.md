# A log forwarder for the IBM Z HMC

[![Version on Pypi](https://img.shields.io/pypi/v/zhmc-log-forwarder.svg)](https://pypi.python.org/pypi/zhmc-log-forwarder/)
[![Docs status (master)](https://readthedocs.org/projects/zhmc-log-forwarder/badge/?version=latest)](https://readthedocs.org/projects/zhmc-log-forwarder/builds/)
[![Test status (master)](https://github.com/zhmcclient/zhmc-log-forwarder/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/zhmcclient/zhmc-log-forwarder/actions/workflows/test.yml?query=branch%3Amaster)
[![Test coverage (master)](https://coveralls.io/repos/github/zhmcclient/zhmc-log-forwarder/badge.svg?branch=master)](https://coveralls.io/github/zhmcclient/zhmc-log-forwarder?branch=master)

# Overview

The zhmc-log-forwarder package provides a log forwarder for the
[IBM Z](https://www.ibm.com/it-infrastructure/z) Hardware Management Console
(HMC), written in pure Python.

It contains a command named `zhmc_log_forwarder` that collects security
logs and audit logs from the Z HMC and forwards the log entries to
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
- [Cloud Auditing Data Federation](https://www.dmtf.org/standards/cadf) (CADF)
  format, represented as a JSON string


# Installation

``` text
$ pip install zhmc-log-forwarder
```

This will install the package and all of its prerequisite packages into
your current Python environment.

It is recommended to use a virtual Python environment, in order not to
clutter up your system Python.

# Quickstart

1.  Make sure you installed the zhmc-log-forwarder package (see the
    previous section).

2.  Create a config file for the `zhmc_log_forwarder` command. The
    config file specifies the targeted HMC, the desired destination for
    the logs, and other data.

    An example config file with explanations of the parameters is shown
    when invoking:

    ``` text
    $ zhmc_log_forwarder --help-config-file
    ```

    Additionally, an example config file is here:
    [example_config_file.yml](https://github.com/zhmcclient/zhmc-log-forwarder/blob/master/example_config_file.yml)

    Redirect that output into a file and edit that file as needed.

3.  Optional: The zhmc-log-forwarder package includes a default HMC log
    message file. That file is used when generating CADF output format
    and defines how the HMC log messages are classified in the CADF
    output. It is possible to specify your own HMC log message file
    using the `log_message_file` parameter in the config file. When
    omitting this parameter, or when setting it to `null`, the default
    HMC log message file included with the zhmc-log-forwarder package is
    used.

    An example HMC log message file explaining its format is shown when
    invoking:

    ``` text
    $ zhmc_log_forwarder --help-log-message-file
    ```

4.  Start the `zhmc_log_forwarder` command as follows:

    ``` text
    $ zhmc_log_forwarder -c CONFIGFILE
    ```

    Where `CONFIGFILE` is the file path of the created config file.

    The command will run forever (or until stopped with Ctrl-C) and will
    forward the log records as specified in the config file.

# Documentation and Change Log

- [Documentation](http://zhmc-log-forwarder.readthedocs.io)
- [Change log](http://zhmc-log-forwarder.readthedocs.io/en/master/changes.html)

# License

The zhmc-log-forwarder package is licensed under the [Apache 2.0
License](https://github.com/zhmcclient/zhmc-log-forwarder/tree/master/LICENSE).
