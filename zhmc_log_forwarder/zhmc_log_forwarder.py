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
A log forwarder for the IBM Z HMC.
"""

import sys
import os
import argparse
from datetime import datetime
import time
from collections import OrderedDict
import textwrap
import logging
from logging.handlers import SysLogHandler
from logging import StreamHandler
import socket
import uuid
import json
import jsonschema

import attr
import yaml
import urllib3
from dateutil import parser as dateutil_parser
from dateutil import tz as dateutil_tz
import stomp
import zhmcclient

from .version import __version__

CMD_NAME = 'zhmc_log_forwarder'
PACKAGE_NAME = 'zhmc-log-forwarder'
BLANKED_SECRET = '********'  # nosec B105

DEST_LOGGER_NAME = CMD_NAME + '_dest'
SELF_LOGGER_NAME = CMD_NAME

# Indent for JSON output to CADF (None=oneline)
CADF_JSON_INDENT = None

# Flag controlling whether optional CADF items are always generated
CADF_ALWAYS_INCLUDE_OPTIONAL_ITEMS = True

# Debug flag: Include full HMC log record in CADF output
DEBUG_CADF_INCLUDE_FULL_RECORD = False

# Debug flag: Output only unknown HMC log messages in CADF output
DEBUG_CADF_ONLY_UNKNOWN = False


try:
    textwrap.indent
except AttributeError:  # undefined function (wasn't added until Python 3.3)
    def indent(text, amount, pad_char=' '):
        """Indent each line of text by amount"""
        pad_str = amount * pad_char
        return ''.join(pad_str + line for line in text.splitlines(True))
else:
    def indent(text, amount, pad_char=' '):
        """Indent each line of text by amount"""
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
    # pylint: disable=redefined-builtin
    """
    Error indicating that there is a connection error either to the HMC or to
    the remote syslog server.
    """
    pass


# JSON schema describing the structure of config files
CONFIG_FILE_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "https://example.com/root.json",
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
        "hmc_verify_cert": {
            "$id": "#/properties/hmc_verify_cert",
            "type": ["boolean", "string"],
            "title": "Controls whether and how the HMC certificate is "
            "verified.",
            "default": True,
            "examples": [
                "true",
                "false",
                "mycerts/ca.pem"
                "mycerts_dir"
            ],
        },
        "stomp_retry_timeout_config": {
            "type": "object",
            "title": "STOMP retry timeout configuration",
            "additionalProperties": False,
            "properties": {
                "connect_timeout": {
                    "type": ["number", "null"],
                    "title": "STOMP connect timeout in seconds. "
                    "This timeout applies to making a connection at the "
                    "socket level. "
                    "The special value 0 means that no timeout is set. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_CONNECT_TIMEOUT.",
                },
                "connect_retries": {
                    "type": ["integer", "null"],
                    "title": "Number of retries (after the initial attempt) "
                    "for STOMP connection-related issues. These retries "
                    "are performed for failed DNS lookups, failed socket "
                    "connections, and socket connection timeouts. "
                    "The special value -1 means that there are infinite "
                    "retries. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_CONNECT_RETRIES.",
                },
                "reconnect_sleep_initial": {
                    "type": ["number", "null"],
                    "title": "Initial STOMP reconnect sleep delay in seconds. "
                    "The reconnect sleep delay is the time to wait before "
                    "reconnecting. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_RECONNECT_SLEEP_INITIAL.",
                },
                "reconnect_sleep_increase": {
                    "type": ["number", "null"],
                    "title": "Factor by which the reconnect sleep delay is "
                    "increased after each connection attempt. "
                    "For example, 0.5 means to wait 50% longer than before "
                    "the previous attempt, 1.0 means wait twice as long, "
                    "and 0 means keep the delay constant. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_RECONNECT_SLEEP_INCREASE.",
                },
                "reconnect_sleep_max": {
                    "type": ["number", "null"],
                    "title": "Maximum reconnect sleep delay in seconds, "
                    "regardless of the 'reconnect_sleep_increase' value. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_RECONNECT_SLEEP_MAX.",
                },
                "reconnect_sleep_jitter": {
                    "type": ["number", "null"],
                    "title": "Random additional time to wait before a "
                    "reconnect to avoid stampeding, as a percentage of the "
                    "current reconnect sleep delay. "
                    "For example, a value of 0.1 means to wait an extra "
                    "0%-10% of the delay calculated using the previous "
                    "three parameters. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_RECONNECT_SLEEP_JITTER.",
                },
                "keepalive": {
                    "type": ["boolean", "null"],
                    "title": "Enable keepalive at the socket level. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_KEEPALIVE.",
                },
                "heartbeat_send_cycle": {
                    "type": ["number", "null"],
                    "title": "Cycle time in which the client will send "
                    "heartbeats to the HMC, in seconds. "
                    "The special value 0 disables the sending of "
                    "heartbeats to the HMC. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_HEARTBEAT_SEND_CYCLE.",
                },
                "heartbeat_receive_cycle": {
                    "type": ["number", "null"],
                    "title": "Cycle time in which the HMC will send "
                    "heartbeats to the client, in seconds. "
                    "The cycle time for the client "
                    "to check the receipt of these heartbeats is that "
                    "time times (1 + 'heartbeat_receive_check'). "
                    "The special value 0 disables heartbeat sending by "
                    "the HMC and checking on the cient side. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_HEARTBEAT_RECEIVE_CYCLE.",
                },
                "heartbeat_receive_check": {
                    "type": ["number", "null"],
                    "title": "Additional time for checking the heartbeats "
                    "received from the HMC on the client, as a percentage "
                    "of the 'heartbeat_receive_cycle' time. For example, "
                    "a value of 0.5 means to wait an extra 50% of the "
                    "'heartbeat_receive_cycle' time. Note that the "
                    "corresponding stomp.py parameter is "
                    "'heart_beat_receive_scale' which is defined as a "
                    "factor. "
                    "The null value will use the default defined in "
                    "zhmcclient.DEFAULT_STOMP_HEARTBEAT_RECEIVE_CHECK.",
                },
            },
        },
        "label": {
            "$id": "#/properties/label",
            "type": ["string", "null"],
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
        "log_message_file": {
            "$id": "#/properties/log_message_file",
            "type": ["string", "null"],
            "title": "File path of HMC log message file (in YAML format) "
            "to be used with the cadf output format. Relative file paths are "
            "relative to the directory containing the config file. "
            "Default is null, which causes the file provided with the "
            "zhmc_log_forwarder package to be used. "
            "Invoke with --help-log-message-file for details.",
            "default": None,
            "examples": [
                "zhmc_log_messages.yml"
            ],
        },
        "check_data": {
            "$id": "#/properties/check_data",
            "type": "object",
            "title": "Data items for additional checks.",
            "default": {},
            "required": [
            ],
            "additionalProperties": False,
            "properties": {
                "imgmt_subnet": {
                    "$id": "#/properties/check_data/properties/"
                    "imgmt_subnet",
                    "type": ["string", "null"],
                    "title": "Subnet of the IMGMT network, in CIDR notation.",
                    "default": None,
                    "examples": [
                        "172.16.192.0/24"
                    ],
                },
                "functional_users": {
                    "$id": "#/properties/check_data/properties/"
                    "functional_users",
                    "type": "array",
                    "title": "List of functional userids.",
                    "default": [],
                    "examples": [
                        "[ zaasmoni, zaasauto ]"
                    ],
                    "items": {
                        "$id": "#/properties/check_data/properties/"
                        "functional_users/items",
                        "type": "string",
                    },
                },
            },
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
                        "title": "Message format for 'line' and 'cadf' output "
                        "formats, as a Python new-style format string. "
                        "Invoke with --help-format-line or --help-format-cadf "
                        "for details on the fields.",
                        "default": "{time:32} {label} {log:8} {name:12} "
                        "{id:>4} {user:20} {msg}",
                        "examples": [
                            "line format: {time:32} {label} {log:8} {name:12} "
                            "{id:>4} {user:20} {msg}"
                            "cadf format: {time} {cadf}"
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


# JSON schema describing the structure of HMC log message files
LOG_MESSAGE_FILE_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "https://example.com/root.json",
    "definitions": {},
    "type": "object",
    "title": "zhmc_log_forwarder HMC log message file",
    "required": [
        "hmc_version",
        "messages",
    ],
    "additionalProperties": False,
    "properties": {
        "hmc_version": {
            "$id": "#/properties/hmc_version",
            "type": "string",
            "title": "HMC version to which this log message file applies",
            "examples": [
                "2.14.1"
            ],
        },
        "messages": {
            "$id": "#/properties/messages",
            "type": "array",
            "title": "List of recognized HMC log messages",
            "items": {
                "$id": "#/properties/messages/items",
                "type": "object",
                "required": [
                    "number",
                    "message",
                    "action",
                    "outcome",
                    "target_type",
                    "target_class",
                ],
                "additionalProperties": False,
                "properties": {
                    "number": {
                        "$id": "#/properties/messages/items/properties/"
                        "number",
                        "type": "string",
                        "title": "event-id / number of HMC log message.",
                        "examples": [
                            "1234"
                        ],
                    },
                    "message": {
                        "$id": "#/properties/messages/items/properties/"
                        "message",
                        "type": "string",
                        "title": "message template of HMC log message.",
                        "examples": [
                            "The user {0} logged on."
                        ],
                    },
                    "action": {
                        "$id": "#/properties/messages/items/properties/"
                        "action",
                        "type": "string",
                        "title": "CADF action. "
                        "See DSP0262 'CADF Action Taxonomy'.",
                        "examples": [
                            "authenticate"
                        ],
                    },
                    "outcome": {
                        "$id": "#/properties/messages/items/properties/"
                        "outcome",
                        "type": "string",
                        "title": "CADF outcome. "
                        "See DSP0262 'CADF Outcome Taxonomy'.",
                        "examples": [
                            "success"
                        ],
                    },
                    "target_type": {
                        "$id": "#/properties/messages/items/properties/"
                        "target_type",
                        "type": "string",
                        "title": "CADF typeURI of target resource. "
                        "See DSP0262 A.2 'CADF Resource Taxonomy'.",
                        "examples": [
                            "service"
                        ],
                    },
                    "target_class": {
                        "$id": "#/properties/messages/items/properties/"
                        "target_class",
                        "type": "string",
                        "title": "HMC resource class of target resource. "
                        "See HMS WS API book, 'class' property of the data "
                        "models.",
                        "examples": [
                            "partition"
                        ],
                    },
                    "initiator_address_item": {
                        "$id": "#/properties/messages/items/properties/"
                        "initiator_address_item",
                        "type": "integer",
                        "title": "Item number of substitution variable in the "
                        "message that is the initiator address. Default: None,"
                        "meaning that the message does not have an initiator "
                        "address.",
                        "examples": [
                            "10.11.12.13"
                        ],
                    },
                },
            },
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
        for prop, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        # pylint: disable=use-yield-from
        yield from validate_properties(validator, properties, instance, schema)

    return jsonschema.validators.extend(
        validator_class, {"properties": set_defaults})


class Config:
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
        return f'Config({parms!r})'

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
            # pylint: disable=unspecified-encoding
            with open(filepath) as fp:
                self._parms = yaml.safe_load(fp)
        except OSError as exc:
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
                    parm_str += f'[{p}]'
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


class LogMessage:
    # pylint: disable=too-few-public-methods
    """
    An HMC log message with sufficient data to allow producing the
    message-specific parts of a CADF event representing the event described by
    the log message.
    """

    def __init__(self, number, message, action, outcome, target_type,
                 target_class, initiator_address_item):

        #: string: event-id / number of HMC log message
        self.number = number

        #: string: message template of HMC log message
        self.message = message

        #: string: CADF action
        #: See DSP0262 A.3 "CADF Action Taxonomy"
        self.action = action

        #: string: CADF outcome
        #: See DSP0262 A.4 "CADF Outcome Taxonomy"
        self.outcome = outcome

        #: string: typeURI of target resource
        #: See DSP0262 A.2 "CADF Resource Taxonomy"
        self.target_type = target_type

        #: string: HMC resource class of target resource
        #: See HMS WS API book, 'class' property of the data models
        #: Example: 'partition'
        self.target_class = target_class

        #: int: Item number of substitution variable in the message that is
        #: the initiator address.
        #: None means that the message does not have an initiator address.
        #: Example: '10.11.12.13'
        self.initiator_address_item = initiator_address_item


class LogMessageConfig(dict):
    """
    HMC log messages to be used, as loaded from HMC log message file.
    """

    def __init__(self):

        # HMC log message file structure, as a JSON schema.
        self._schema = LOG_MESSAGE_FILE_SCHEMA

        # Data from the HMC log message file.
        self._data = None

        # Messages from the file, as a dict of LogMessage objects, by
        # message number.
        self._messages = None

    def __repr__(self):
        data = dict(self._data)
        return f'LogMessageConfig({data!r})'

    @property
    def messages(self):
        """
        The HMC log messages recognized by the the HMC log message file, as a
        dict of LogMessage objects, by message number.
        """
        return self._messages

    def load_message_file(self, filepath):
        """
        Load the HMC log message file (a YAML file) and set the corresponding
        attributes of this object. Omitted properties are defaulted to the
        defaults defined in the JSON schema.

        Parameters:

          filepath (string): File path of the HMC log message file.
        """

        # Load HMC log message file
        try:
            # pylint: disable=unspecified-encoding
            with open(filepath) as fp:
                self._data = yaml.safe_load(fp)
        except OSError as exc:
            raise UserError(
                "Cannot load HMC log message file {}: {}".
                format(filepath, exc))

        # Use a validator that adds defaults for omitted parameters
        ValidatorWithDefaults = extend_with_default(jsonschema.Draft7Validator)
        validator = ValidatorWithDefaults(self._schema)

        # Validate structure of loaded config parms
        try:
            validator.validate(self._data)
        except jsonschema.exceptions.ValidationError as exc:
            item_str = ''
            for p in exc.absolute_path:
                # Path contains list index numbers as integers
                if isinstance(p, int):
                    item_str += f'[{p}]'
                else:
                    if item_str != '':
                        item_str += '.'
                    item_str += p
            raise UserError(
                "HMC log message file {file} contains an invalid item {item}: "
                "{msg} (Validation details: Schema item: {schema_item}; "
                "Failing validator: {val_name}={val_value})".
                format(
                    file=filepath,
                    msg=exc.message,
                    item=item_str,
                    schema_item='.'.join(exc.absolute_schema_path),
                    val_name=exc.validator,
                    val_value=exc.validator_value))

        # Set up the other attributes

        self._messages = dict()
        messages = self._data['messages']
        for m in messages:
            number = m['number']
            m_obj = LogMessage(
                number=number,
                message=m['message'],
                action=m['action'],
                outcome=m['outcome'],
                target_type=m['target_type'],
                target_class=m['target_class'],
                initiator_address_item=m.get('initiator_address_item', None)
            )
            self._messages[number] = m_obj


class HelpConfigFileAction(argparse.Action):
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-config-file.
    """

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

# HMC certificate validation:
# - true (default): CA certificates in the Python 'certifi' package.
# - false: Disable CA certificate validation.
# - str: Path to CA PEM file or CA directory (with c_rehash links).
hmc_verify_cert: mycerts/ca.pem

# STOMP retry/timeout configuration.
# null means to use the zhmcclient defaults.
# For a description, see
# https://python-zhmcclient.readthedocs.io/en/latest/notifications.html#zhmcclient.StompRetryTimeoutConfig
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

    # Format for 'line' and 'cadf' output formats, as a Python new-style format
    # string. Invoke with --help-format-line or --help-format-cadf for details.
    # Typical setting for 'line' format:
    line_format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'
    # Typical setting for 'cadf' format:
    # line_format: '{time} {label} {cadf}'

    # Format for the 'time' field in the log message, as a Python
    # datetime.strftime() format string, or one of: 'iso8601', 'iso8601b',
    # or 'syslog'.
    # Invoke with --help-time-format for details.
    # Typical setting for 'line' format:
    time_format: 'iso8601'
    # Typical setting for 'cadf' format:
    # time_format: 'syslog'
""")
        sys.exit(2)


class HelpLogMessageFileAction(argparse.Action):
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-log-message-file.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        print("""---
# HMC log message file for the zhmc_log_forwarder command, in YAML format.
#
# This file defines information about HMC log messages that allows translating
# an HMC log message received from the HMC into a CADF event.
#
# For a list of the possible HMC log messages, see the Help system of a real
# HMC, in section "Introduction" -> "Audit, Event, and Security Log Messages".
#
# For the CADF standard DSP0262, see
# https://www.dmtf.org/sites/default/files/standards/documents/DSP0262_1.0.0.pdf
#
# The data specified for each HMC log message in this file, is:
# * number (string): event-id / number of HMC log message.
# * message (string): message template of HMC log message.
# * action (string): CADF action. See DSP0262 "CADF Action Taxonomy".
# * outcome (string): CADF outcome. See DSP0262 "CADF Outcome Taxonomy".
# * target_type (string): CADF typeURI of target resource. See DSP0262
#   A.2 "CADF Resource Taxonomy".
# * target_class (string): HMC resource class of target resource. See HMS WS
#   API book, 'class' property of the data models. Example: 'partition'.
# * initiator_address_item (integer): Item number of substitution variable in
#   the message that is the initiator IP address. None means that the message
#   does not have an initiator address. Default: None.

# HMC version to which this HMC log message file applies
hmc_version: "2.14.1"

# The HMC log messages that will be recognized by zhmc_log_forwarder
messages:
  -
    number: '1408'
    message: "User {0} has logged on from location {3} ..."
    action: authenticate/logon/gui
    outcome: success
    target_type: service
    target_class: console
    initiator_address_item: 3
  -
    number: '1801'
    message: "The user template {0} was added"
    action: create
    outcome: success
    target_type: service
    target_class: user_template
""")
        sys.exit(2)


class HelpFormatAction(argparse.Action):
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-format.
    """

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
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-format-line.
    """

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

* var_values: The list of values of the substitution variables for the log
  message. The item number is the index into the list. Missing items are
  represented with value None.

  The substitution variables for each log message (including their item
  numbers) are described in the help system of the HMC, in topic 'Introduction'
  -> 'Audit, Event, and Security Log Messages'.

* var_types: The list of data type names of the substitution variables for the
  log message. The item number is the index into the list. Missing items are
  represented with value None. Possible data type names are: 'long', 'float',
  'string'.

Example:

    format: '{time:32} {label} {log:8} {name:12} {id:>4} {user:20} {msg}'
""")
        sys.exit(2)


class HelpFormatCADFAction(argparse.Action):
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-format-cadf.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
For output format 'cadf', each log record is formatted as a single line whose
content is defined in the 'line_format' parameter in the config file.

The value of that config parameter is a Python new-style format string, using
predefined names for the fields of the log message.

While the fields can be arbitrarily selected and ordered in the format string,
the format string that should be used is:

    {time} {label} {cadf}

Supported fields:

* time: The time stamp of the log entry, as reported by the HMC in the log
  entry data. This is the time stamp that is also shown in the HMC GUI.
  The format of this field is defined in the 'time_format' parameter in the
  config file.
  Invoke with --help-time-format for details.

* label: The label for the HMC that was specified in the 'label' config
  parameter.

* cadf: The single-line JSON string that conforms to the CADF standard
  (DMTF standard DSP0262).

The following is an example log record in 'cadf' output format. For ease of
reading, the JSON string has been formatted across multiple lines. In the
actual record that is sent, it will be all on a single line:

Nov 25 18:06:37 wdc04-05.HMC1
{
    "id": "zhmc_log_forwarder:e3c43ae3-037b-4b64-9721-3242ea94c9e7",
    "typeURI": "https://schemas.dmtf.org/cloud/audit/1.0/event",
    "eventTime": "2019-11-25T19:06:37+0100",
    "eventType": "activity",
    "action": "authenticate/logon",
    "outcome": "success",
    "observer": {
        "id": "hmc:/api/console",
        "typeURI": "service",
        "name": "HMC1",
        "x_label": "wdc04-05.HMC1"
    },
    "x_message": {
        "number": "1941",
        "log": "security",
        "text": "User zbcInstall has logged on to Web Services API ...",
        "variables": [
            [
                "zbcInstall",
                "string"
            ],
            [
                "Sx9feb3000-e9e7-11e9-bf4a-00106f237ab1.53dd",
                "string"
            ],
            [
                "10.183.204.141",
                "string"
            ]
        ]
    },
    "x_check_data": {
        "imgmt_subnet": "172.16.192.0/24",
        "functional_users": [
            "zaasmoni",
            "zaasauto"
        ]
    },
    "initiator": {
        "id": "hmc:/api/users/1c114a6a-dba3-11e8-8643-00106f237ab1",
        "typeURI": "data/security/account/user",
        "name": "zbcInstall"
    },
    "target": {
        "id": "hmc:/api/console",
        "typeURI": "service",
        "name": "HMC1",
        "x_class": "console"
    }
}

""")
        sys.exit(2)


class HelpTimeFormatAction(argparse.Action):
    # pylint: disable=too-few-public-methods
    """
    Argparse class providing help text for --help-time-format.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The format for the 'time' field in the output for each log message is defined
in the 'time_format' parameter in the config file, using a Python
datetime.strftime() format string, or alternatively the following keywords:

- iso8601: ISO 8601 format with 'T' as delimiter,
  e.g. 2019-08-09T12:46:38.550000+02:00
- iso8601b: ISO 8601 format with ' ' as delimiter,
  e.g. 2019-08-09 12:46:38.550000+02:00
- syslog: Syslog time format, e.g. Nov 25 18:06:37
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
        usage=f"{CMD_NAME} [options]",
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
        '--help-log-message-file',
        action=HelpLogMessageFileAction, nargs=0,
        help="Show help about the HMC log message file format and exit.")
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
        action='version', version=f'{CMD_NAME} {__version__}',
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
class LogEntry:
    # pylint: disable=too-few-public-methods
    """
    Definition of the data maintained for a log entry. This data is independent
    of output formatting.
    """
    time = attr.attrib(type=datetime)  # Time stamp as datetime object
    label = attr.attrib(type=str)  # HMC label
    log = attr.attrib(type=str)  # HMC log (security, audit)
    name = attr.attrib(type=str)  # Name of the log entry
    id = attr.attrib(type=int)  # ID of the log entry
    user_name = attr.attrib(type=str)  # Name of HMC userid for log entry
    user_id = attr.attrib(type=str)  # Object-ID of HMC userid for log entry
    msg = attr.attrib(type=str)  # Formatted message
    var_values = attr.attrib(type=list)  # List of subst.var values in message
    var_types = attr.attrib(type=list)  # List of subst.var types in message
    full_record = attr.attrib(type=dict)  # Dict with full HMC log record


def formatted_time(dt, time_format):
    """
    Return a string that is the formatted input time `dt`, using the
    time format specified in the 'time_format' field.
    """
    if time_format == 'iso8601':
        return dt.isoformat()
    if time_format == 'iso8601b':
        return dt.isoformat(' ')
    if time_format == 'syslog':
        time_format = '%b %d %H:%M:%S'
    return dt.strftime(time_format)  # already checked in __init__()


class OutputHandler:
    """
    Handle the outputting of log records for a single log forwarding.
    """

    def __init__(self, config_parms, log_message_config, fwd_parms):
        """
        Parameters:

          config_parms (dict): Configuration parameters, overall.

          log_message_config (LogMessageConfig): HMC log messages for CADF
            output format, or None for other output formats.

          fwd_parms (dict): Configuration parameters for the forwarding.
            Some of the more relevant fields are:
            * format: line / cadf - output format
        """
        self.config_parms = config_parms
        self.log_message_config = log_message_config
        self.fwd_parms = fwd_parms

        props = CONFIG_FILE_SCHEMA['properties']['check_data']['properties']
        data = self.config_parms.get('check_data', OrderedDict())
        if 'imgmt_subnet' not in data:
            data['imgmt_subnet'] = props['imgmt_subnet']['default']
        if 'functional_users' not in data:
            data['functional_users'] = props['functional_users']['default']
        self.check_data = data

        self.logger = None

        label_hdr = 'Label'
        label = self.config_parms['label']
        self.label_len = max(len(label_hdr), len(label))
        self.label_hdr = label_hdr.ljust(self.label_len)
        self.label = label.ljust(self.label_len)

        # Attributes that are set when logging to syslog
        self.syslog_host = None
        self.syslog_port = None
        self.syslog_facility = None
        self.syslog_porttype = None

        fwd_format = self.fwd_parms['format']

        if fwd_format == 'line':
            # Check validity of the line_format string:
            line_format = self.fwd_parms['line_format']
            try:
                line_format.format(
                    time='test', label='test', log='test', name='test',
                    id='test', user='test', msg='test', var_values='test',
                    var_types='test')
            except KeyError as exc:
                # KeyError is raised when the format string contains a named
                # placeholder that is not provided in format().
                raise UserError(
                    "Config parameter 'line_format' in forwarding '{name}' "
                    "specifies an invalid field: {msg}".
                    format(name=self.fwd_parms['name'], msg=str(exc)))

        # Check validity of the time_format string:
        dt = datetime.now()
        time_format = self.fwd_parms['time_format']
        try:
            formatted_time(dt, time_format)
        except UnicodeError as exc:
            raise UserError(
                "Config parameter 'time_format' is invalid: {}".
                format(str(exc)))

    def output_begin(self):
        """
        Called once at begin of outputting any records.

        Can be used for writing header information to the destination (e.g.
        a table header in case of stdout), or for initializing attributes or
        resources such as Python loggers (e.g. when writing to syslog).
        """
        dest = self.fwd_parms['dest']
        fwd_format = self.fwd_parms['format']
        line_format = self.fwd_parms['line_format']
        if dest in ('stdout', 'stderr'):
            if fwd_format == 'line':
                dest_stream = getattr(sys, dest)
                out_str = line_format.format(
                    time='Time', label=self.label_hdr, log='Log', name='Name',
                    id='ID', user='Userid', msg='Message',
                    var_values='Variables',
                    var_types='Variable types')
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
        """
        Called once at end of outputting any records.

        Can be used for writing footer information to the destination (e.g.
        a table header in case of stdout), or for cleaning up resources such
        as Python loggers (e.g. when writing to syslog).
        """
        dest = self.fwd_parms['dest']
        fwd_format = self.fwd_parms['format']
        if dest in ('stdout', 'stderr'):
            if fwd_format == 'line':
                dest_stream = getattr(sys, dest)
                print("-" * 120, file=dest_stream)
                dest_stream.flush()
        else:
            assert dest == 'syslog'
            # Loggers do not need to be cleaned up

    def output_entries(self, log_entries, console):
        """
        Called for outputting a set of log records.
        Can be called multiple times.
        """
        table = []
        for le in log_entries:
            le_log = le['log-type']
            if le_log not in self.fwd_parms['logs']:
                continue
            hmc_time = le['event-time']
            le_time = zhmcclient.datetime_from_timestamp(
                hmc_time, dateutil_tz.tzlocal())
            le_name = le['event-name']
            le_id = le['event-id']
            le_user_name = le['userid'] or ''
            le_user_id = le['user-uri'] or ''
            le_msg = le['event-message']

            # Convert the data items into two index-correlated lists, for
            # value and type. The logic tolerates missing and unsorted
            # item numbers.
            le_var_values = []
            le_var_types = []
            data_items = le['event-data-items']
            if data_items:
                data_items = sorted(data_items,
                                    key=lambda i: i['data-item-number'])
                max_item_number = data_items[-1]['data-item-number']
                di = 0
                for i in range(0, max_item_number + 1):
                    data_item = data_items[di]
                    if i == data_item['data-item-number']:
                        le_var_values.append(data_item['data-item-value'])
                        le_var_types.append(data_item['data-item-type'])
                        di += 1
                    else:
                        # Item at this index is missing. This has not been
                        # observed in any actual log messages so far.
                        le_var_values.append(None)
                        le_var_types.append(None)

            row = LogEntry(
                time=le_time, label=self.label, log=le_log, name=le_name,
                id=le_id, user_name=le_user_name, user_id=le_user_id,
                msg=le_msg, var_values=le_var_values, var_types=le_var_types,
                full_record=le)
            table.append(row)

        sorted_table = sorted(table, key=lambda row: row.time)

        dest = self.fwd_parms['dest']
        if dest in ('stdout', 'stderr'):
            dest_stream = getattr(sys, dest)
            for row in sorted_table:
                out_str = self.out_str(row, console)
                if out_str:
                    print(out_str, file=dest_stream)
                    dest_stream.flush()
        else:
            assert dest == 'syslog'
            for row in sorted_table:
                out_str = self.out_str(row, console)
                if out_str:
                    try:
                        self.logger.info(out_str)
                    except Exception as exc:
                        raise ConnectionError(
                            "Cannot write log entry to syslog server at "
                            "{host}, port {port}/{porttype}: {msg}".
                            format(host=self.syslog_host, port=self.syslog_port,
                                   porttype=self.syslog_porttype, msg=str(exc)))

    def out_str(self, row, console):
        """
        Return an output string for the specified row that fits the specified
        output format.

        If the row is not to be output, None is returned.
        """
        fwd_format = self.fwd_parms['format']
        time_format = self.fwd_parms['time_format']
        if fwd_format == 'line':
            line_format = self.fwd_parms['line_format']
            out_str = line_format.format(
                time=formatted_time(row.time, time_format),
                label=row.label,
                log=row.log, name=row.name, id=row.id, user=row.user_name,
                msg=row.msg, var_values=row.var_values,
                var_types=row.var_types)
        else:
            assert fwd_format == 'cadf'
            assert isinstance(self.log_message_config, LogMessageConfig)
            assert isinstance(console, zhmcclient.Console)
            try:
                msg_info = self.log_message_config.messages[row.id]
            except KeyError:
                msg_info = LogMessage(
                    number=None,
                    message=None,
                    action='unknown',
                    outcome='unknown',
                    target_type=None,
                    target_class=None,
                    initiator_address_item=None,
                )
            if DEBUG_CADF_ONLY_UNKNOWN and msg_info.action != 'unknown':
                return None
            msg_id = str(uuid.uuid4())
            out_dict = OrderedDict([
                ("id", f"zhmc_log_forwarder:{msg_id}"),
                ("typeURI", "https://schemas.dmtf.org/cloud/audit/1.0/event"),
                ("eventTime", formatted_time(row.time, 'iso8601')),
                ("eventType", "activity"),
                ("action", msg_info.action),
                ("x_eventCategory", "activity/" + msg_info.action),
                ("x_eventType", "zhmc" + row.id),
                ("outcome", msg_info.outcome),
                ("observer", OrderedDict([
                    ("id", f"hmc:{console.uri}"),
                    ("typeURI", "service"),
                    ("name", console.name),
                    ("x_label", row.label),
                ])),
                ("x_message", OrderedDict([
                    ("number", row.id),
                    ("log", row.log),
                    ("text", row.msg),
                    ("var_values", row.var_values),
                    ("var_types", row.var_types),
                ])),
                ("x_check_data", self.check_data),
            ])
            if row.user_name or CADF_ALWAYS_INCLUDE_OPTIONAL_ITEMS:
                initiator = OrderedDict([
                    ("id", f"hmc:{row.user_id}"),
                    ("typeURI", "data/security/account/user"),
                    ("name", row.user_name),
                ])
                # Try to find out initiator IP address
                ix = msg_info.initiator_address_item
                if ix is None:
                    initiator_address = "unknown"
                else:
                    initiator_address = row.var_values[ix]
                if "console" in initiator_address:
                    # e.g. "the console"
                    initiator_address = "console"
                if "unknown" in initiator_address:
                    # e.g. "an unknown location"
                    initiator_address = "unknown"
                initiator["address"] = initiator_address
                out_dict["initiator"] = initiator
            if msg_info.target_type or CADF_ALWAYS_INCLUDE_OPTIONAL_ITEMS:
                if msg_info.target_class == 'console':
                    resource_id = f"hmc:{console.uri}"
                    resource_name = console.name
                else:
                    # TODO: Change id to use object-id of HMC target resource
                    resource_id = "hmc:{TODO:resource.object-id}"
                    # TODO: Change name to use name of HMC target resource
                    resource_name = "{TODO:resource.name}"
                out_dict["target"] = OrderedDict([
                    ("id", resource_id),
                    ("typeURI", msg_info.target_type),
                    ("name", resource_name),
                    ("x_class", msg_info.target_class),
                ])
            if DEBUG_CADF_INCLUDE_FULL_RECORD:
                out_dict["x_full_record"] = row.full_record
            cadf_str = json.dumps(out_dict, indent=CADF_JSON_INDENT)
            line_format = self.fwd_parms['line_format']
            out_str = line_format.format(
                time=formatted_time(row.time, time_format),
                label=row.label,
                cadf=cadf_str)
        return out_str


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


class SelfLogger:
    """
    Python logger for self-logging.

    Self-logging is the logging of any actions and particularly of failures of
    this program itself. This is separate from forwarding the HMC log entries.

    At this point, self-logging can be configured to go to stdout or stderr,
    and the log message format and time format for the log message can be
    configured.
    """

    def __init__(self, dest, format_str, time_format, debug):
        """
        Parameters:

          dest (string): The name of the self-logging destination, as a string
            ('stdout', 'stderr').

          format_str (string): The format string for self-logging, using Python
            logging.Formatter string format.

          time_format (string): The format string for the 'asctime' field
            in the format string, using datetime.strftime() format.

          debug (bool): Show debug self-logged messages. This causes causes the
            log level to be increased from INFO to DEBUG.
        """
        self._dest = dest
        self._format = format_str
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
        """Log at debug level"""
        self._setup()
        self._logger.debug(msg)

    def info(self, msg):
        """Log at info level"""
        self._setup()
        self._logger.info(msg)

    def warning(self, msg):
        """Log at warning level"""
        self._setup()
        self._logger.warning(msg)

    def error(self, msg):
        """Log at error level"""
        self._setup()
        self._logger.error(msg)


def zhmcclient_log_setup(logger_name, dest, format_str, time_format, debug):
    """
    Set up the zhmcclient loggers.
    """
    formatter = DatetimeFormatter(
        fmt=format_str, datefmt=time_format)
    if dest == 'stdout':
        dest_stream = sys.stdout
    else:
        assert dest == 'stderr'
        dest_stream = sys.stderr
    handler = StreamHandler(dest_stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    log_level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(log_level)


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


def process_future(
        self_logger, session, console, out_handlers, all_logs,
        hmc, userid, password, stomp_rt_config):
    """
    Process future items
    """
    topic_items = session.get_notification_topics()
    security_topic_name = None
    audit_topic_name = None
    topic_names = []
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
        try:
            receiver = zhmcclient.NotificationReceiver(
                topic_names, hmc, userid, password,
                stomp_rt_config=stomp_rt_config)
        except stomp.exception.StompException as exc:
            self_logger.error(
                "Cannot create notification receiver: {}: {}".
                format(exc.__class__.__name__, exc))
            raise

        try:  # make sure the receiver gets closed
            self_logger.info(
                "Starting to wait for future log entries")
            while True:
                try:
                    for headers, message in receiver.notifications():
                        if headers['notification-type'] == 'log-entry':
                            topic_name = headers['destination'].split('/')[-1]
                            if topic_name == security_topic_name:
                                log_entries = message['log-entries']
                                for le in log_entries:
                                    le['log-type'] = 'security'
                                for hdlr in out_handlers:
                                    hdlr.output_entries(log_entries, console)
                            elif topic_name == audit_topic_name:
                                log_entries = message['log-entries']
                                for le in log_entries:
                                    le['log-type'] = 'audit'
                                for hdlr in out_handlers:
                                    hdlr.output_entries(log_entries, console)
                            else:
                                self_logger.warning(
                                    "Ignoring invalid topic name: {}".
                                    format(topic_name))
                        else:
                            self_logger.warning(
                                "Ignoring invalid notification type: {}".
                                format(headers['notification-type']))
                    self_logger.warning(
                        "Unexpected end of receiver.notifications() "
                        "loop - starting loop again")
                    time.sleep(5)
                except zhmcclient.NotificationError as exc:
                    self_logger.warning(
                        "Reconnecting after notification error: {}: {}".
                        format(exc.__class__.__name__, exc))
                except stomp.exception.StompException as exc:
                    self_logger.warning(
                        "Reconnecting after STOMP error: {}: {}".
                        format(exc.__class__.__name__, exc))
        except KeyboardInterrupt:
            for hdlr in out_handlers:
                hdlr.output_end()
            self_logger.info(
                "Received keyboard interrupt - stopping to wait "
                "for future log entries")
        finally:
            self_logger.info(
                "Closing notification receiver")
            try:
                receiver.close()
            except zhmcclient.Error as exc:
                self_logger.warning(
                    "Ignoring error when closing notification receiver: {}".
                    format(exc))


def main():
    """
    Main routine of the program.
    """

    urllib3.disable_warnings()  # Used by zhmcclient

    # Initial self-logger, using defaults.
    # This is needed for errors during config processing.
    top_schema_props = CONFIG_FILE_SCHEMA['properties']
    self_logger = SelfLogger(
        dest=top_schema_props['selflog_dest']['default'],
        format_str=top_schema_props['selflog_format']['default'],
        time_format=top_schema_props['selflog_time_format']['default'],
        debug=False)

    try:  # transform any of our exceptions to an error exit

        args = parse_args()

        config = Config()
        config.load_config_file(args.config_file)

        # Final self-logger, using configuration parameters.
        self_logger = SelfLogger(
            dest=config.parms['selflog_dest'],
            format_str=config.parms['selflog_format'],
            time_format=config.parms['selflog_time_format'],
            debug=args.debug)

        zhmcclient_log_setup(
            logger_name=zhmcclient.JMS_LOGGER_NAME,
            dest=config.parms['selflog_dest'],
            format_str=config.parms['selflog_format'],
            time_format=config.parms['selflog_time_format'],
            debug=args.debug)

        # self_logger.debug("Effective config with defaults: {!r}".
        #                   format(config))

        stomp_rt_config = zhmcclient.StompRetryTimeoutConfig(
            **config.parms['stomp_retry_timeout_config'])

        hmc = config.parms['hmc_host']
        userid = config.parms['hmc_user']
        password = config.parms['hmc_password']
        verify_cert = config.parms['hmc_verify_cert']
        label = config.parms['label']
        since = config.parms['since']
        future = config.parms['future']

        log_message_file = config.parms['log_message_file']
        if log_message_file:
            if not os.path.isabs(log_message_file):
                config_dir = os.path.dirname(args.config_file)
                log_message_file = os.path.join(config_dir, log_message_file)
        else:
            my_dir = os.path.dirname(__file__)
            log_message_file = os.path.join(my_dir, 'zhmc_log_messages.yml')
        log_message_config = LogMessageConfig()
        log_message_config.load_message_file(log_message_file)

        if since == 'all':
            begin_time = None
            since_str = 'all'
        elif since == 'now':
            begin_time = datetime.now(dateutil_tz.tzlocal())
            since_str = f'now ({begin_time})'
        else:
            assert since is not None
            try:
                begin_time = dateutil_parser.parse(since)
                # TODO: Pass tzinfos arg to get timezones parsed. Without that,
                # only UTC is parsed, and anything else will lead to no tzinfo.
                if begin_time.tzinfo is None:
                    begin_time = begin_time.replace(
                        tzinfo=dateutil_tz.tzlocal())
                since_str = f'{begin_time}'
            except (ValueError, OverflowError):
                raise UserError(
                    "Config parameter 'since' has an invalid date & time "
                    "value: {}".
                    format(args.since))

        self_logger.info(
            f"{CMD_NAME} starting")
        self_logger.info(
            f"{CMD_NAME} version: {__version__}")
        self_logger.info(
            "Config file: {file}".
            format(file=args.config_file))
        self_logger.info(
            "HMC log message file for CADF: {file}".
            format(file=log_message_file))
        self_logger.info(
            "HMC: {host}, Userid: {user}, Label: {label}".
            format(host=hmc, user=userid, label=label))
        self_logger.info(
            "Since: {since}, Future: {future}".
            format(since=since_str, future=future))

        out_handlers = []
        all_logs = set()
        for fwd_parms in config.parms['forwardings']:

            name = fwd_parms['name']
            logs = fwd_parms['logs']
            dest = fwd_parms['dest']
            fwd_format = fwd_parms['format']
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

            self_logger.info(
                "Forwarding: '{name}'; Logs: {logs}; Destination: {dest}; "
                "Format: {fmt}".
                format(name=name, logs=', '.join(logs), dest=dest_str,
                       fmt=fwd_format))

            hdlr = OutputHandler(config.parms, log_message_config, fwd_parms)
            out_handlers.append(hdlr)

            for log in logs:
                all_logs.add(log)

        self_logger.info(
            "Collecting these logs altogether: {logs}".
            format(logs=', '.join(all_logs)))

        try:  # make sure the session gets logged off

            session = zhmcclient.Session(
                hmc, userid, password, verify_cert=verify_cert)
            client = zhmcclient.Client(session)
            console = client.consoles.console

            for hdlr in out_handlers:
                hdlr.output_begin()

            log_entries = get_log_entries(
                all_logs, console, begin_time=begin_time, end_time=None)
            for hdlr in out_handlers:
                hdlr.output_entries(log_entries, console)

            if future:
                process_future(
                    self_logger, session, console, out_handlers, all_logs,
                    hmc, userid, password, stomp_rt_config)
            else:
                for hdlr in out_handlers:
                    hdlr.output_end()
        except KeyboardInterrupt:
            pass
        finally:
            self_logger.info(
                "Logging off from HMC")
            try:
                session.logoff()
            except zhmcclient.Error as exc:
                self_logger.warning(
                    "Ignoring error when logging off from HMC: {}".
                    format(exc))
    except (Error, zhmcclient.Error) as exc:
        self_logger.error(str(exc))
        sys.exit(1)

    self_logger.info(
        f"{CMD_NAME} stopped")


if __name__ == '__main__':
    main()
