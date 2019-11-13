#!/usr/bin/env python
# Copyright 2019-2019 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A log forwarder for the IBM Z HMC.
"""

from __future__ import print_function
import sys
import argparse
from datetime import datetime
import textwrap
import logging
from logging.handlers import SysLogHandler
from logging import StreamHandler
import socket
import jsonschema

import attr
import pbr
import yaml
import requests.packages.urllib3
from dateutil import parser as dateutil_parser
from dateutil import tz as dateutil_tz
import zhmcclient

CMD_NAME = 'zhmc_log_forwarder'
PACKAGE_NAME = 'zhmc-log-forwarder'
__version__ = pbr.version.VersionInfo(PACKAGE_NAME).release_string()
BLANKED_SECRET = '********'

DEST_LOGGER_NAME = CMD_NAME + '_dest'
SELF_LOGGER_NAME = CMD_NAME
SELF_LOGGER = None  # Will be initialized in main()

try:
    textwrap.indent
except AttributeError:  # undefined function (wasn't added until Python 3.3)
    def indent(text, amount, pad_char=' '):
        pad_str = amount * pad_char
        return ''.join(pad_str + line for line in text.splitlines(True))
else:
    def indent(text, amount, pad_char=' '):
        return textwrap.indent(text, amount * pad_char)


class Error(Exception):
    """
    Abstract base class for any errors raised by this program.
    """
    pass


class UserError(Error):
    """
    Error indicating that the user of the program made an error.
    """
    pass


class ConnectionError(Error):
    """
    Error indicating that there is a connection error either to the HMC or to
    the remote syslog server.
    """
    pass


# JSON schema describing the structure of config files
CONFIG_FILE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/root.json",
    "definitions": {},
    "type": "object",
    "title": "zhmc_log_forwarder config file",
    "required": [
        "hmc_host",
        "hmc_user",
        "hmc_password",
    ],
    "additionalProperties": False,
    "properties": {
        "hmc_host": {
            "$id": "#/properties/hmc_host",
            "type": "string",
            "title": "IP address or hostname of the HMC",
            "examples": [
                "10.11.12.13"
            ],
        },
        "hmc_user": {
            "$id": "#/properties/hmc_user",
            "type": "string",
            "title": "HMC userid",
            "examples": [
                "myuser"
            ],
        },
        "hmc_password": {
            "$id": "#/properties/hmc_password",
            "type": "string",
            "title": "HMC password",
            "examples": [
                "mypassword"
            ],
        },
        "label": {
            "$id": "#/properties/label",
            "type": "string",
            "title": "Label for the HMC to be used in log message "
            "(as field 'label').",
            "default": None,
            "examples": [
                "myregion-myzone-myhmc"
            ],
        },
        "since": {
            "$id": "#/properties/since",
            "type": "string",
            "title": "Point in time since when log entries are to be "
            "included, as follows:"
            " - 'now': Include past log entries since now. This may "
            "actually include log entries from recent past.",
            " - 'all': Include all available past log entries."
            " - A date and time value suitable for dateutil.parser. "
            "Timezones are ignored and the local timezone is assumed "
            "instead."
            "default": "now",
            "examples": [
                "now", "all", "13:00", "2018-08-11 16:00"
            ],
        },
        "future": {
            "$id": "#/properties/future",
            "type": "boolean",
            "title": "Wait for future log entries",
            "default": False,
            "examples": [
                True, False
            ]
        },
        "selflog_dest": {
            "$id": "#/properties/selflog_dest",
            "type": "string",
            "title": "Destination for any self-log messages, as follows:"
            " - 'stdout': Standard output."
            " - 'stderr': Standard error.",
            "enum": ["stdout", "stderr"],
            "default": "stdout",
            "examples": [
                "stdout", "stderr"
            ],
        },
        "selflog_format": {
            "$id": "#/properties/selflog_format",
            "type": "string",
            "title": "Format of any self-log messages, as a format string for "
            "Python logging.Formatter objects. See "
            "https://docs.python.org/2/library/logging.html#"
            "logrecord-attributes for details.",
            "default": "%(levelname)s: %(message)s",
            "examples": [
                "%(levelname)s: %(message)s"
            ],
        },
        "selflog_time_format": {
            "$id": "#/properties/selflog_time_format",
            "type": "string",
            "title": "Format for the 'asctime' field of any self-log "
            "messages, as a Python datetime.strftime() format string. "
            "Invoke with --help-time-format for details.",
            "default": "%Y-%m-%d %H:%M:%S.%f%z",
            "examples": [
                "%Y-%m-%d %H:%M:%S.%f%z"
            ],
        },
        "forwardings": {
            "$id": "#/properties/forwardings",
            "type": "array",
            "title": "List of log forwardings",
            "default": [],
            "items": {
                "$id": "#/properties/forwardings/items",
                "type": "object",
                "required": [
                    "name",
                    "logs",
                    "dest",
                ],
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/name",
                        "type": "string",
                        "title": "Name of the log forwarding (unique within "
                        "a configuration).",
                        "examples": [
                            "Example forwarding"
                        ],
                    },
                    "logs": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/logs",
                        "type": "array",
                        "title": "List of HMC logs to include in the log "
                        "forwarding. Allowable values for the list items:"
                        " - 'security': HMC Security Log."
                        " - 'audit': HMC Audit Log.",
                        "default": [
                            "security",
                            "audit"
                        ],
                        "items": {
                            "$id": "#/properties/forwardings/items/"
                            "properties/logs/items",
                            "type": "string",
                            "enum": [
                                "security",
                                "audit"
                            ],
                            "examples": [
                                "security",
                                "audit"
                            ],
                        }
                    },
                    "dest": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/dest",
                        "type": "string",
                        "title": "Destination of the log forwarding. "
                        "Allowable values:"
                        " - 'stdout': Standard output."
                        " - 'stderr': Standard error."
                        " - 'syslog': Local or remote system log.",
                        "enum": [
                            "stdout", "stderr", "syslog"
                        ],
                        "examples": [
                            "stdout", "stderr", "syslog"
                        ],
                    },
                    "syslog_host": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/syslog_host",
                        "type": ["string", "null"],
                        "title": "IP address or hostname of the syslog "
                        "server, for syslog destinations.",
                        "default": None,
                        "examples": [
                            "10.11.12.14"
                        ],
                    },
                    "syslog_port": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/syslog_port",
                        "type": "integer",
                        "title": "Port number of the syslog server, "
                        "for syslog destinations.",
                        "default": 514,
                        "examples": [
                            514
                        ]
                    },
                    "syslog_porttype": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/syslog_porttype",
                        "type": "string",
                        "title": "Port type of the syslog server, "
                        "for syslog destinations.",
                        "enum": [
                            "tcp", "udp"
                        ],
                        "default": "tcp",
                        "examples": [
                            "tcp", "udp"
                        ],
                    },
                    "syslog_facility": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/syslog_facility",
                        "type": "string",
                        "title": "Facility name for the syslog server, "
                        "for syslog destinations.",
                        "enum": [
                            'user', 'auth', 'authpriv', 'security', 'local0',
                            'local1', 'local2', 'local3', 'local4', 'local5',
                            'local6', 'local7'
                        ],
                        "default": "user",
                        "examples": [
                            "user"
                        ],
                    },
                    "format": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/format",
                        "type": "string",
                        "title": "Output format for the log records. "
                        "Invoke with --help-format for details.",
                        "enum": [
                            'line', 'cadf'
                        ],
                        "default": "line",
                        "examples": [
                            "line"
                        ],
                    },
                    "line_format": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/line_format",
                        "type": "string",
                        "title": "Message format for 'line' output format, "
                        "as a Python new-style format string. "
                        "Invoke with --help-format-line for "
                        "details on the fields.",
                        "default": "{time:32} {label} {log:8} {name:12} "
                        "{id:>4} {user:20} {msg}",
                        "examples": [
                            "{time:32} {label} {log:8} {name:12} {id:>4} "
                            "{user:20} {msg}"
                        ],
                    },
                    "time_format": {
                        "$id": "#/properties/forwardings/items/"
                        "properties/time_format",
                        "type": "string",
                        "title": "Format for any time fields in the log "
                        "records (for all output formats), as a Python "
                        "datetime.strftime() format string. "
                        "Invoke with --help-time-format for details.",
                        "default": "%Y-%m-%d %H:%M:%S.%f%z",
                        "examples": [
                            "%Y-%m-%d %H:%M:%S.%f%z"
                        ],
                    }
                }
            }
        }
    }
}


def extend_with_default(validator_class):
    """
    Factory function that returns a new JSON schema validator class that
    extends the specified class by the ability to update the JSON instance
    that is being validated, by adding the schema-defined default values for
    any omitted properties.

    Courtesy: https://python-jsonschema.readthedocs.io/en/stable/faq/

    Parameters:

      validator_class (jsonschema.IValidator): JSON schema validator class
        that will be extended.

    Returns:

      jsonschema.IValidator: JSON schema validator class that has been
        extended.
    """
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(
            validator, properties, instance, schema,
        ):
            yield error

    return jsonschema.validators.extend(
        validator_class, {"properties": set_defaults},
    )


class Config(object):
    """
    The configuration parameters.
    """

    def __init__(self):

        # Config file structure, as a JSON schema.
        self._schema = CONFIG_FILE_SCHEMA

        # Config parameter values, as the top level object of the configuration
        # file (i.e. a dict).
        # Parameters not specified in the configuration file are defaulted
        # using the defaults from the JSON schema.
        self._parms = None

    def __repr__(self):
        parms = dict(self._parms)
        parms['hmc_password'] = BLANKED_SECRET
        return 'Config({!r})'.format(parms)

    @property
    def parms(self):
        """
        The configuration parameters, as a dictionary representing the
        top-level object in the config file (i.e. the top-level properties
        are items in that top-level dictionary).
        """
        return self._parms

    def load_config_file(self, filepath):
        """
        Load a YAML config file and set the configuration parameters of this
        object. Omitted properties are defaulted to the defaults defined in
        the JSON schema.

        Parameters:

          filepath (string): File path of the config file.
        """

        # Load config file
        try:
            with open(filepath, 'r') as fp:
                self._parms = yaml.safe_load(fp)
        except IOError as exc:
            raise UserError(
                "Cannot load config file {}: {}".
                format(filepath, exc))

        # Use a validator that adds defaults for omitted parameters
        ValidatorWithDefaults = extend_with_default(jsonschema.Draft7Validator)
        validator = ValidatorWithDefaults(self._schema)

        # Validate structure of loaded config parms
        try:
            validator.validate(self._parms)
        except jsonschema.exceptions.ValidationError as exc:
            parm_str = ''
            for p in exc.absolute_path:
                # Path contains list index numbers as integers
                if isinstance(p, int):
                    parm_str += '[{}]'.format(p)
                else:
                    if parm_str != '':
                        parm_str += '.'
                    parm_str += p
            raise UserError(
                "Config file {file} contains an invalid item {parm}: {msg} "
                "(Validation details: Schema item: {schema_item}; "
                "Failing validator: {val_name}={val_value})".
                format(
                    file=filepath,
                    msg=exc.message,
                    parm=parm_str,
                    schema_item='.'.join(exc.absolute_schema_path),
                    val_name=exc.validator,
                    val_value=exc.validator_value))


class HelpConfigFileAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""---
# Config file for the zhmc_log_forwarder command, in YAML format.

# This is an example config file with all supported config parameters and their
# descriptions. You need to edit the file for setting at least the hmc_*
# and syslog_* parameters.

# IP address or hostname of the HMC.
hmc_host: 10.11.12.13

# HMC userid.
hmc_user: myuser

# HMC password.
hmc_password: mypassword

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

# Destination for any self-log entries:
# - 'stdout': Standard output.
# - 'stderr': Standard error.
selflog_dest: stdout

# Format of any self-log entries, as a format string for Python
# logging.Formatter objects.
# See https://docs.python.org/2/library/logging.html#logrecord-attributes for
# details.
selflog_format: '%(levelname)s: %(message)s'

# Format for the 'asctime' field of any self-log entries, as a Python
# datetime.strftime() format string.
# Invoke with --help-time-format for details.
selflog_time_format: '%Y-%m-%d %H:%M:%S.%f%z'

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

    # Format for 'line' output format, as a Python new-style format string.
    # Invoke with --help-format-line for details.
    line_format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'

    # Format for the 'time' field in the log message, as a Python
    # datetime.strftime() format string.
    # Invoke with --help-time-format for details.
    time_format: '%Y-%m-%d %H:%M:%S.%f%z'
""")
        sys.exit(2)


class HelpFormatAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The format for each log record that is sent to the destination is defined in
the 'format' parameter in the config file, using these choices:

    line  - Single line for each record, using the format defined in the
            'line_format' parameter in the config file.
            Invoke with --help-format-line for details.

    cadf  - CADF format, as a JSON string.
            Invoke with --help-format-cadf for details.
""")
        sys.exit(2)


class HelpFormatLineAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
For output format 'line', each log record is formatted as a single line whose
content is defined in the 'line_format' parameter in the config file.

The value of that config parameter is a Python new-style format string, using
predefined names for the fields of the log message.

The fields can be arbitrarily selected and ordered in the format string, and
the complete syntax for replacement fields in new-style format strings can be
used to determine for example adjustment, padding or conversion.

Supported fields:

* time: The time stamp of the log entry, as reported by the HMC in the log
  entry data. This is the time stamp that is also shown in the HMC GUI.
  The format of this field is defined in the 'time_format' parameter in the
  config file.
  Invoke with --help-time-format for details.

* label: The label for the HMC that was specified in the 'label' config
  parameter.

* log: The HMC log to which this log entry belongs: security, audit.

* name: The name of the log entry if it has one, or the empty string otherwise.

* id: The ID of the log entry.

* user: The HMC userid associated with the log entry, or the empty string if
  no user is associated with it.

* msg: The fully formatted log message, in English.

* msg_vars: The substitution variables used in the log message, represented as
  a list of items in the order of their index numbers. Each list item is
  a tuple of (value, type). Possible types are: 'long', 'float', 'string'.

  The substitution variables for each log message (including their index
  numbers) are described in the help system of the HMC, in topic 'Introduction'
  -> 'Audit, Event, and Security Log Messages'.

* detail_msgs: The list of fully formatted detail log messages, in English.
  Detail messages are rarely present.

* detail_msgs_vars: The substitution variables used in the detail log messages.
  This is a list of items for each detail message in the same order as
  in field 'detail_msgs', where each item is a list of substitution variables
  used in the corresponding detail log message. Each item in that inner list
  is a tuple of (value, type). Possible types are: 'long', 'float', 'string'.

Example:

    format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'
""")
        sys.exit(2)


class HelpFormatCADFAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
For output format 'cadf', each log record is formatted as a JSON string
that conforms to the CADF standard (DMTF standard DSP0262).

The following is an example log record in 'cadf' output format:

  {
      "typeURI": "http://schemas.dmtf.org/cloud/audit/1.0/event",
      "eventTime": "2019-06-22T13:00:00-04:00",
      "eventType": "activity",
      "action": "authenticate/login",
      "initiator": {
          "typeURI": "data/security/account/user",
          "name": "exampleuser@ibm.com",
          "host": {
              "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) \
AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.87 \
Safari/537.36",
              "address": "192.168.1.1"
          }
      },
      "target": {
          "id": "12",
          "name": "LPAR123",
          "type": "Partition"
      },
      "observer": {
          "id":  "target",
          "name": "HM-1-Example-Host-Name"
      },
      "outcome": "failure",
      "reason": {
          "reasonType": "HTTP",
          "reasonCode": "401"
      }
  }
""")
        sys.exit(2)


class HelpTimeFormatAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The format for the 'time' field in the output for each log message is defined
in the 'time_format' parameter in the config file, using a Python
datetime.strftime() format string, or alternatively the following keywords:

- iso8601: ISO 8601 format with 'T' as delimiter,
  e.g. 2019-08-09T12:46:38.550000+02:00
- iso8601b: ISO 8601 format with ' ' as delimiter,
  e.g. 2019-08-09 12:46:38.550000+02:00
- Any other value is interpreted as datetime.strftime() format string.

The format for the 'asctime' field in any self-logged messages is defined in
the 'selflog_time_format' parameter in the config file, also using a Python
datetime.strftime() format string.

The syntax for datetime.strftime() format strings is described here:
https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior

The datetime objects used for these time stamps are timezone-aware, using the
local timezone of the system on which this program runs. Any locale-specific
components in the datetime.strftime() format string are created using the
locale of the system on which this program runs (e.g. the name of weekdays).

Examples:

    time_format: '%Y-%m-%d %H:%M:%S.%f%z'
    time_format: iso8601   # only for 'time' field of log messages
""")
        sys.exit(2)


def parse_args():
    """
    Create and configure an argument parser using the Python argparse module
    and parse the command line arguments.

    Returns:
        argparse.Namespace: Dictionary with parsing results.
    """

    parser = argparse.ArgumentParser(
        add_help=False,
        description="A log forwarder for the IBM Z HMC. "
        "The log entries can be selected based on HMC log type (e.g. Security "
        "log, Audit log) and based on the point in time since when past log "
        "entries should be forwarded. "
        "It is possible to wait in a loop for future log entries to be "
        "created."
        "Destinations can be standard output, standard error, or a syslog "
        "server. Multiple destinations are supported in parallel, e.g. "
        "the HMC Audit log can be sent to a QRadar syslog server, and "
        "both the HMC Audit log and Security log can be sent to a logDNA "
        "syslog server.",
        usage="{} [options]".format(CMD_NAME),
        epilog=None)

    general_opts = parser.add_argument_group('General options')
    general_opts.add_argument(
        '-h', '--help',
        action='help', default=argparse.SUPPRESS,
        help="Show this help message and exit.")
    general_opts.add_argument(
        '--help-config-file',
        action=HelpConfigFileAction, nargs=0,
        help="Show help about the config file format and exit.")
    general_opts.add_argument(
        '--help-format',
        action=HelpFormatAction, nargs=0,
        help="Show help about the output formats and exit.")
    general_opts.add_argument(
        '--help-format-line',
        action=HelpFormatLineAction, nargs=0,
        help="Show help about the 'line' output format and exit.")
    general_opts.add_argument(
        '--help-format-cadf',
        action=HelpFormatCADFAction, nargs=0,
        help="Show help about the 'cadf' output format and exit.")
    general_opts.add_argument(
        '--help-time-format',
        action=HelpTimeFormatAction, nargs=0,
        help="Show help about the time field formatting and exit.")
    general_opts.add_argument(
        '--version',
        action='version', version='{} {}'.format(CMD_NAME, __version__),
        help="Show the version number of this program and exit.")
    general_opts.add_argument(
        '--debug',
        dest='debug', action='store_true',
        help="Show debug self-logged messages (if any).")

    config_opts = parser.add_argument_group('Config options')
    config_opts.add_argument(
        '-c', '--config-file', metavar="CONFIGFILE",
        required=True,
        dest='config_file', action='store',
        help="File path of the config file to use.")

    args = parser.parse_args()
    return args


@attr.attrs
class LogEntry(object):
    """
    Definition of the data maintained for a log entry. This data is independent
    of output formatting.
    """
    time = attr.attrib(type=datetime)  # Time stamp as datetime object
    label = attr.attrib(type=str)  # HMC label
    log = attr.attrib(type=str)  # HMC log (security, audit)
    name = attr.attrib(type=str)  # Name of the log entry
    id = attr.attrib(type=int)  # ID of the log entry
    user = attr.attrib(type=str)  # HMC userid associated with log entry
    msg = attr.attrib(type=str)  # Formatted message
    msg_vars = attr.attrib(type=list)  # List of subst.vars in message
    detail_msgs = attr.attrib(type=list)  # List of formatted detail messages
    detail_msgs_vars = attr.attrib(type=list)  # List of list of subst.vars


class OutputHandler(object):
    """
    Handle the outputting of log records for a single log forwarding.
    """

    def __init__(self, config_parms, fwd_parms):
        """
        Parameters:

          config_parms (dict): Configuration parameters, overall.

          fwd_parms (dict): Configuration parameters for the forwarding.
        """
        self.config_parms = config_parms
        self.fwd_parms = fwd_parms

        self.logger = None

        label_hdr = 'Label'
        label = self.config_parms['label']
        self.label_len = max(len(label_hdr), len(label))
        self.label_hdr = label_hdr.ljust(self.label_len)
        self.label = label.ljust(self.label_len)

        format = self.fwd_parms['format']
        if format == 'cadf':
            raise NotImplementedError
            # TODO: Implement support for CADF

        # Check validity of the line_format string:
        line_format = self.fwd_parms['line_format']
        try:
            line_format.format(
                time='test', label='test', log='test', name='test', id='test',
                user='test', msg='test', msg_vars='test',
                detail_msgs='test', detail_msgs_vars='test')
        except KeyError as exc:
            # KeyError is raised when the format string contains a named
            # placeholder that is not provided in format().
            raise UserError(
                "Config parameter 'line_format' in forwarding '{name}' "
                "specifies an invalid field: {msg}".
                format(name=self.fwd_parms['name'], msg=str(exc)))

        # Check validity of the time_format string:
        dt = datetime.now()
        try:
            self.formatted_time(dt)
        except UnicodeError as exc:
            raise UserError(
                "Config parameter 'time_format' is invalid: {}".
                format(str(exc)))

    def formatted_time(self, dt):
        time_format = self.fwd_parms['time_format']
        if time_format == 'iso8601':
            return dt.isoformat()
        if time_format == 'iso8601b':
            return dt.isoformat(' ')
        return dt.strftime(time_format)  # already checked in __init__()

    def output_begin(self):
        dest = self.fwd_parms['dest']
        line_format = self.fwd_parms['line_format']
        if dest in ('stdout', 'stderr'):
            dest_stream = getattr(sys, dest)
            out_str = line_format.format(
                time='Time', label=self.label_hdr, log='Log', name='Name',
                id='ID', user='Userid', msg='Message',
                msg_vars='Message variables', detail_msgs='Detail messages',
                detail_msgs_vars='Detail messages variables')
            print(out_str, file=dest_stream)
            print("-" * 120, file=dest_stream)
            dest_stream.flush()
        else:
            assert dest == 'syslog'
            self.syslog_host = self.fwd_parms['syslog_host']
            self.syslog_port = self.fwd_parms['syslog_port']
            self.syslog_facility = self.fwd_parms['syslog_facility']
            assert self.syslog_facility in SysLogHandler.facility_names
            facility_code = SysLogHandler.facility_names[self.syslog_facility]
            self.syslog_porttype = self.fwd_parms['syslog_porttype']
            if self.syslog_porttype == 'tcp':
                # Newer syslog protocols, e.g. rsyslog
                socktype = socket.SOCK_STREAM
            else:
                assert self.syslog_porttype == 'udp'
                # Older syslog protocols, e.g. BSD
                socktype = socket.SOCK_DGRAM
            try:
                handler = SysLogHandler(
                    (self.syslog_host, self.syslog_port), facility_code,
                    socktype=socktype)
            except Exception as exc:
                raise ConnectionError(
                    "Cannot create log handler for syslog server at "
                    "{host}, port {port}/{porttype}: {msg}".
                    format(host=self.syslog_host, port=self.syslog_port,
                           porttype=self.syslog_porttype, msg=str(exc)))
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger = logging.getLogger(DEST_LOGGER_NAME)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def output_end(self):
        dest = self.fwd_parms['dest']
        if dest in ('stdout', 'stderr'):
            dest_stream = getattr(sys, dest)
            print("-" * 120, file=dest_stream)
            dest_stream.flush()
        else:
            assert dest == 'syslog'
            pass  # nothing to do

    def output_entries(self, log_entries):
        table = list()
        for le in log_entries:
            le_log = le['log-type']
            if le_log not in self.fwd_parms['logs']:
                continue
            hmc_time = le['event-time']
            le_time = zhmcclient.datetime_from_timestamp(
                hmc_time, dateutil_tz.tzlocal())
            le_name = le['event-name']
            le_id = le['event-id']
            le_user = le['userid'] or ''
            le_msg = le['event-message']
            data_items = le['event-data-items']
            data_items = sorted(data_items,
                                key=lambda i: i['data-item-number'])
            le_msg_vars = [(i['data-item-value'], i['data-item-type'])
                           for i in data_items]
            le_detail_msgs = []  # TODO: Implement detail messages
            le_detail_msgs_vars = []  # TODO: Implement detail messages vars.
            row = LogEntry(
                time=le_time, label=self.label, log=le_log, name=le_name,
                id=le_id, user=le_user, msg=le_msg, msg_vars=le_msg_vars,
                detail_msgs=le_detail_msgs,
                detail_msgs_vars=le_detail_msgs_vars)
            table.append(row)
        sorted_table = sorted(table, key=lambda row: row.time)
        dest = self.fwd_parms['dest']
        line_format = self.fwd_parms['line_format']
        if dest in ('stdout', 'stderr'):
            dest_stream = getattr(sys, dest)
            for row in sorted_table:
                out_str = line_format.format(
                    time=self.formatted_time(row.time), label=row.label,
                    log=row.log, name=row.name, id=row.id, user=row.user,
                    msg=row.msg, msg_vars=row.msg_vars,
                    detail_msgs=row.detail_msgs,
                    detail_msgs_vars=row.detail_msgs_vars)
                print(out_str, file=dest_stream)
                dest_stream.flush()
        else:
            assert dest == 'syslog'
            for row in sorted_table:
                out_str = line_format.format(
                    time=self.formatted_time(row.time), label=row.label,
                    log=row.log, name=row.name, id=row.id, user=row.user,
                    msg=row.msg, msg_vars=row.msg_vars,
                    detail_msgs=row.detail_msgs,
                    detail_msgs_vars=row.detail_msgs_vars)
                try:
                    self.logger.info(out_str)
                except Exception as exc:
                    raise ConnectionError(
                        "Cannot write log entry to syslog server at "
                        "{host}, port {port}/{porttype}: {msg}".
                        format(host=self.syslog_host, port=self.syslog_port,
                               porttype=self.syslog_porttype, msg=str(exc)))


class DatetimeFormatter(logging.Formatter):
    """
    Python log formatter that uses datetime for time formatting.

    The reason to have a special formatter is that the time formatting
    implemented by the standard Python logging.Formatter uses time.strftime()
    which does not support microseconds.

    This log formatter overrides its formatTime() method to use
    datetime.strftime() instead. The timezone is set to the local timezone.
    """

    def formatTime(self, record, datefmt=None):
        # record (LogRecord): Has the time at which the log record was created
        #   in the following attributes:
        #   - record.created (float): Seconds since the epoch. Precision varies
        #     by system and may or may not include a sub-second value.
        #   - record.msecs (int): Milliseconds within the second
        time_value = record.created
        if time_value.is_integer():
            time_value += float(record.msecs) / 1000
        dt = datetime.fromtimestamp(time_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dateutil_tz.tzlocal())
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S.%f%z")
        return s


class SelfLogger(object):
    """
    Python logger for self-logging.

    Self-logging is the logging of any actions and particularly of failures of
    this program itself. This is separate from forwarding the HMC log entries.

    At this point, self-logging can be configured to go to stdout or stderr,
    and the log message format and time format for the log message can be
    configured.
    """

    def __init__(self, dest, format, time_format, debug):
        """
        Parameters:

          dest (string): The name of the self-logging destination, as a string
            ('stdout', 'stderr').

          format (string): The format string for self-logging, using Python
            logging.Formatter string format.

          time_format (string): The format string for the 'asctime' field
            in the format string, using datetime.strftime() format.

          debug (bool): Show debug self-logged messages. This causes causes the
            log level to be increased from INFO to DEBUG.
        """
        self._dest = dest
        self._format = format
        self._time_format = time_format
        self._debug = debug

        self._logger = None  # Lazy initialization

    def _setup(self):
        """
        Set up the logger, if not yet set up.
        """
        if self._logger is None:
            formatter = DatetimeFormatter(
                fmt=self._format, datefmt=self._time_format)
            if self._dest == 'stdout':
                dest_stream = sys.stdout
            else:
                assert self._dest == 'stderr'
                dest_stream = sys.stderr
            handler = StreamHandler(dest_stream)
            handler.setFormatter(formatter)
            self._logger = logging.getLogger(SELF_LOGGER_NAME)
            self._logger.addHandler(handler)
            log_level = logging.DEBUG if self._debug else logging.INFO
            self._logger.setLevel(log_level)

    def debug(self, msg):
        self._setup()
        self._logger.debug(msg)

    def info(self, msg):
        self._setup()
        self._logger.info(msg)

    def warning(self, msg):
        self._setup()
        self._logger.warning(msg)

    def error(self, msg):
        self._setup()
        self._logger.error(msg)


def get_log_entries(logs, console, begin_time, end_time):
    """
    Retrieve the desired types of log entries for a specified time range from
    the HMC.
    """
    log_entries = []
    if 'audit' in logs:
        audit_entries = console.get_audit_log(begin_time, end_time)
        for e in audit_entries:
            e['log-type'] = 'audit'
        log_entries += audit_entries
    if 'security' in logs:
        security_entries = console.get_security_log(begin_time, end_time)
        for e in security_entries:
            e['log-type'] = 'security'
        log_entries += security_entries
    return log_entries


def main():
    """
    Main routine of the program.
    """

    requests.packages.urllib3.disable_warnings()  # Used by zhmcclient

    # Initial self-logger, using defaults.
    # This is needed for errors during config processing.
    top_schema_props = CONFIG_FILE_SCHEMA['properties']
    SELF_LOGGER = SelfLogger(
        dest=top_schema_props['selflog_dest']['default'],
        format=top_schema_props['selflog_format']['default'],
        time_format=top_schema_props['selflog_time_format']['default'],
        debug=False)

    try:  # transform any of our exceptions to an error exit

        args = parse_args()

        config = Config()
        config.load_config_file(args.config_file)

        # Final self-logger, using configuration parameters.
        SELF_LOGGER = SelfLogger(
            dest=config.parms['selflog_dest'],
            format=config.parms['selflog_format'],
            time_format=config.parms['selflog_time_format'],
            debug=args.debug)

        # SELF_LOGGER.debug("Effective config with defaults: {!r}".
        #                   format(config))

        hmc = config.parms['hmc_host']
        userid = config.parms['hmc_user']
        password = config.parms['hmc_password']
        label = config.parms['label']
        since = config.parms['since']
        future = config.parms['future']

        if since == 'all':
            begin_time = None
            since_str = 'all'
        elif since == 'now':
            begin_time = datetime.now(dateutil_tz.tzlocal())
            since_str = 'now ({})'.format(begin_time)
        else:
            assert since is not None
            try:
                begin_time = dateutil_parser.parse(since)
                # TODO: Pass tzinfos arg to get timezones parsed. Without that,
                # only UTC is parsed, and anything else will lead to no tzinfo.
                if begin_time.tzinfo is None:
                    begin_time = begin_time.replace(
                        tzinfo=dateutil_tz.tzlocal())
                since_str = '{}'.format(begin_time)
            except (ValueError, OverflowError) as exc:
                raise UserError(
                    "Config parameter 'since' has an invalid date & time "
                    "value: {}".
                    format(args.since))

        SELF_LOGGER.info(
            "{} starting".format(CMD_NAME))
        SELF_LOGGER.info(
            "{} version: {}".format(CMD_NAME, __version__))
        SELF_LOGGER.info(
            "HMC: {host}, Userid: {user}, Label: {label}".
            format(host=hmc, user=userid, label=label))
        SELF_LOGGER.info(
            "Since: {since}, Future: {future}".
            format(since=since_str, future=future))

        out_handlers = []
        all_logs = set()
        for fwd_parms in config.parms['forwardings']:

            name = fwd_parms['name']
            logs = fwd_parms['logs']
            dest = fwd_parms['dest']
            format = fwd_parms['format']
            syslog_host = fwd_parms['syslog_host']
            syslog_port = fwd_parms['syslog_port']
            syslog_porttype = fwd_parms['syslog_porttype']
            syslog_facility = fwd_parms['syslog_facility']

            if dest in ('stdout', 'stderr'):
                dest_str = dest
            else:
                assert dest == 'syslog'
                dest_str = "{} (server {}, port {}/{}, facility {})". \
                    format(dest, syslog_host, syslog_port, syslog_porttype,
                           syslog_facility)

            SELF_LOGGER.info(
                "Forwarding: '{name}'; Logs: {logs}; Destination: {dest}; "
                "Format: {format}".
                format(name=name, logs=', '.join(logs), dest=dest_str,
                       format=format))

            out_handler = OutputHandler(config.parms, fwd_parms)
            out_handlers.append(out_handler)

            for log in logs:
                all_logs.add(log)

        SELF_LOGGER.info(
            "Collecting these logs altogether: {logs}".
            format(logs=', '.join(all_logs)))

        try:  # make sure the session gets logged off

            session = zhmcclient.Session(hmc, userid, password)
            client = zhmcclient.Client(session)
            console = client.consoles.console

            for hdlr in out_handlers:
                hdlr.output_begin()

            log_entries = get_log_entries(
                all_logs, console, begin_time=begin_time, end_time=None)
            for hdlr in out_handlers:
                hdlr.output_entries(log_entries)

            if future:
                topic_items = session.get_notification_topics()
                security_topic_name = None
                audit_topic_name = None
                topic_names = list()
                for topic_item in topic_items:
                    topic_type = topic_item['topic-type']
                    if topic_type == 'security-notification' \
                            and 'security' in all_logs:
                        security_topic_name = topic_item['topic-name']
                        topic_names.append(security_topic_name)
                    if topic_type == 'audit-notification' \
                            and 'audit' in all_logs:
                        audit_topic_name = topic_item['topic-name']
                        topic_names.append(audit_topic_name)
                if topic_names:
                    receiver = zhmcclient.NotificationReceiver(
                        topic_names, hmc, userid, password)
                    try:  # make sure the receiver gets closed
                        SELF_LOGGER.info(
                            "Starting to wait for future log entries")
                        while True:
                            for headers, message in receiver.notifications():
                                if headers['notification-type'] == 'log-entry':
                                    topic_name = headers['destination']. \
                                        split('/')[-1]
                                    if topic_name == security_topic_name:
                                        log_entries = message['log-entries']
                                        for le in log_entries:
                                            le['log-type'] = 'security'
                                        for hdlr in out_handlers:
                                            hdlr.output_entries(log_entries)
                                    elif topic_name == audit_topic_name:
                                        log_entries = message['log-entries']
                                        for le in log_entries:
                                            le['log-type'] = 'audit'
                                        for hdlr in out_handlers:
                                            hdlr.output_entries(log_entries)
                                    else:
                                        SELF_LOGGER.warning(
                                            "Ignoring invalid topic name: {}".
                                            format(topic_name))
                                else:
                                    SELF_LOGGER.warning(
                                        "Ignoring invalid notification type: "
                                        "{}".
                                        format(headers['notification-type']))
                            SELF_LOGGER.warning(
                                "Notification receiver has disconnected - "
                                "reopening")
                    except KeyboardInterrupt:
                        out_handler.output_end()
                        SELF_LOGGER.info(
                            "Received keyboard interrupt - stopping to wait "
                            "for future log entries")
                    finally:
                        SELF_LOGGER.info(
                            "Closing notification receiver")
                        try:
                            receiver.close()
                        except zhmcclient.Error as exc:
                            SELF_LOGGER.warning(
                                "Ignoring error when closing notification "
                                "receiver: {}".format(exc))
            else:
                out_handler.output_end()
        except KeyboardInterrupt:
            pass
        finally:
            SELF_LOGGER.info(
                "Logging off from HMC")
            try:
                session.logoff()
            except zhmcclient.Error as exc:
                SELF_LOGGER.warning(
                    "Ignoring error when logging off from HMC: {}".
                    format(exc))
    except (Error, zhmcclient.Error) as exc:
        SELF_LOGGER.error(str(exc))
        sys.exit(1)

    SELF_LOGGER.info(
        "{} stopped".format(CMD_NAME))


if __name__ == '__main__':
    main()
