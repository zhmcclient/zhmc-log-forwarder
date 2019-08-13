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

import sys
import argparse
from datetime import datetime
from collections import OrderedDict
import textwrap
import logging
from logging.handlers import SysLogHandler
from logging import StreamHandler
import socket

import attr
import pbr
import yaml
import requests.packages.urllib3
from dateutil import parser, tz
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
    Abstract base class for any errors raised by this script.
    """
    pass


class UserError(Error):
    """
    Error indicating that the user of the script made an error.
    """
    pass


class ConnectionError(Error):
    """
    Error indicating that there is a connection error either to the HMC or to
    the remote syslog server.
    """
    pass


@attr.attrs
class ConfigParm(object):
    """
    Definition of a single config parameter for this script.

    They may be specified in a config file and overridden using command line
    options. This definition represents the resulting effective configuration,
    i.e. "required" means the parameter is required to be defined in the config
    file or in the command line (or both).
    """
    type = attr.attrib(type=str)  # type in text form for including in help
    desc = attr.attrib(type=str)  # description text for help
    allowed = attr.attrib(type=list, default=None)  # list of allowed values
    required = attr.attrib(type=bool, default=False)  # required or optional
    default = attr.attrib(type=str, default=None)  # default value if optional
    example = attr.attrib(type=object, default=None)  # example value
    secret = attr.attrib(type=bool, default=False)  # blanked out on display


# Definition of all configuration parameters for this script.
CONFIG_PARMS = OrderedDict()
CONFIG_PARMS['hmc_host'] = ConfigParm(
    type='string',
    required=True, example='10.11.12.13',
    desc="IP address or hostname of the HMC.")
CONFIG_PARMS['hmc_user'] = ConfigParm(
    type='string',
    required=True, example='myuser',
    desc="HMC userid.")
CONFIG_PARMS['hmc_password'] = ConfigParm(
    type='string',
    required=True, example='mypassword', secret=True,
    desc="HMC password.")
CONFIG_PARMS['label'] = ConfigParm(
    type='string',
    required=False, default=None, example='myregion-myzone-myhmc',
    desc="Label for this HMC to be used in log output (as field 'label').")
CONFIG_PARMS['logs'] = ConfigParm(
    type='list/tuple of string',
    allowed=['security', 'audit'],
    required=False, default=['security', 'audit'],
    desc="""
List of log types to include, with the following list item values:
- 'security': HMC Security Log."
- 'audit': HMC Audit Log.
""")
CONFIG_PARMS['since'] = ConfigParm(
    type='string',
    required=False, default='now',
    desc="""
Include past log entries since the specified date and time, or since a special
date and time.
Values are:
- A date and time value suitable for dateutil.parser. Timezones are ignored
  and the local timezone is assumed instead.
- 'all': Include all available past log entries.
- 'now': Include past log entries since now. This may actually include log
  entries from recent past.
""")
CONFIG_PARMS['future'] = ConfigParm(
    type='bool',
    required=False, default=True,
    desc="""
Wait for future log entries. Use keyboard interrupt (e.g. Ctrl-C) to stop the
program.
""")
CONFIG_PARMS['dest'] = ConfigParm(
    type='string',
    allowed=['stdout', 'syslog'],
    required=False, default='stdout',
    desc="""
Destination for the log entries:
- 'stdout': Standard output.
- 'syslog': Local or remote system log.
""")
CONFIG_PARMS['syslog_host'] = ConfigParm(
    type='string',
    required=False, default=None, example='10.11.12.14',
    desc="""
IP address or hostname of the remote syslog server, for dest=syslog.
""")
CONFIG_PARMS['syslog_port'] = ConfigParm(
    type='int',
    required=False, default=514,
    desc="""
Port number of the remote syslog server, for dest=syslog.
""")
CONFIG_PARMS['syslog_porttype'] = ConfigParm(
    type='string',
    allowed=['tcp', 'udp'],
    required=False, default='udp',
    desc="""
Port type of the remote syslog server, for dest=syslog.
""")
CONFIG_PARMS['syslog_facility'] = ConfigParm(
    type='string',
    allowed=['user', 'auth', 'authpriv', 'security', 'local0', 'local1',
             'local2', 'local3', 'local4', 'local5', 'local6', 'local7'],
    required=False, default='user',
    desc="""
Syslog facility name, for dest=syslog.
""")
CONFIG_PARMS['format'] = ConfigParm(
    type='string',
    required=False,
    default='{time:32} {label} {type:8} {name:12} {id:>4} {user:20} {msg}',
    desc="""
Format of the output for each log entry, as a Python new-style format string.
Invoke with --help-output-format for details on the fields.
""")
CONFIG_PARMS['time_format'] = ConfigParm(
    type='string',
    required=False,
    default='%Y-%m-%d %H:%M:%S.%f%z',
    desc="""
Format for the 'time' field in the output for each log entry, as a Python
datetime.strftime() format string.
Invoke with --help-time-format for details.
""")
CONFIG_PARMS['selflog_dest'] = ConfigParm(
    type='string',
    allowed=['stdout', 'stderr'],
    required=False, default='stdout',
    desc="""
Destination for any self-log entries:
- 'stdout': Standard output.
- 'stderr': Standard error.
""")
CONFIG_PARMS['selflog_format'] = ConfigParm(
    type='string',
    required=False,
    default='%(levelname)s: %(message)s',
    desc="""
Format of any self-log entries, as a format string for Python logging.Formatter
objects.
See https://docs.python.org/2/library/logging.html#logrecord-attributes for
details.
""")
CONFIG_PARMS['selflog_time_format'] = ConfigParm(
    type='string',
    required=False,
    default='%Y-%m-%d %H:%M:%S.%f%z',
    desc="""
Format for the 'asctime' field of any self-log entries, as a Python
datetime.strftime() format string.
Invoke with --help-time-format for details.
""")


class Config(object):
    """
    The configuration for this script. It can be set from a config file and/or
    from command line options.

    The configuration parameters are attributes on an object of this class.
    See CONFIG_PARMS for details.
    """

    def __init__(self):

        # Config parameters: dict of name to value.
        # Parameters not specified are omitted from the dict.
        self.parms = dict()

        # Set defaults of optional parameters
        for name in CONFIG_PARMS:
            parm = CONFIG_PARMS[name]
            if not parm.required:
                self.parms[name] = parm.default

    def __repr__(self):

        # Blank out secret config parms
        parms_copy = dict(self.parms)
        for name in self.parms:
            parm = CONFIG_PARMS[name]
            if parm.secret:
                parms_copy[name] = BLANKED_SECRET

        return 'Config({!r})'.format(parms_copy)

    def update_from_file(self, filepath):
        """
        Update the configuration from a config file in YAML.

        The config file must have only the config parameters for this config
        class. Additional parameters will cause UserError to be raised.
        """
        try:
            with open(filepath, 'r') as fp:
                config_dict = yaml.safe_load(fp)
        except IOError as exc:
            raise UserError(
                "Cannot load config file {}: {}".
                format(filepath, exc))
        for name in config_dict:
            value = config_dict[name]
            if name not in CONFIG_PARMS:
                raise UserError(
                    "Config file {} contains an invalid config parameter: "
                    "{} = {}".
                    format(filepath, name, value))
            else:
                self.set_parm(name, value, 'config file')

    def update_from_args(self, args):
        """
        Update the configuration from parsed command line arguments.

        The args parameter must contain the config parameters as attributes.
        It may contain additional attributes, only those attributes that
        are config parameters are used.
        """
        for name in CONFIG_PARMS:
            if hasattr(args, name):
                value = getattr(args, name)
                if value is not None:
                    self.set_parm(name, value, 'command line')

    def set_parm(self, name, value, source):
        """
        Set a config parameter to a value.

        'source' is a human readable indicator for the source of the
        config parameter.
        """
        parm = CONFIG_PARMS[name]
        if parm.allowed is not None:
            assert not parm.secret
            if parm.type.startswith('list'):
                if not all(v in parm.allowed for v in value):
                    raise UserError(
                        "Config parameter '{}' from {} has an invalid "
                        "value: {} (allowed is a list of any of: {}).".
                        format(name, source, value, ', '.join(parm.allowed)))
            else:
                if value not in parm.allowed:
                    raise UserError(
                        "Config parameter '{}' from {} has an invalid "
                        "value: {} (allowed values are: {}).".
                        format(name, source, value, ', '.join(parm.allowed)))
        self.parms[name] = value

    def get_parm(self, name):
        """
        Return the value of a config parameter.

        If it is required and not specified, a UserError is raised.
        """
        try:
            value = self.parms[name]
        except KeyError:
            parm = CONFIG_PARMS[name]
            if parm.required:
                raise UserError(
                    "Required config parameter '{}' was not specified "
                    "(in config file or command line).".
                    format(name))
        return value


class HelpConfigAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The configuration consists of the following parameters. They can be specified
in a config file and as optiona on the command line. Command line options
override config file parameters.

The statements below about whether a parameter is required or optional refer
to the effective configuration after applying the config file and the command
line options.""")
        for name in CONFIG_PARMS:
            parm = CONFIG_PARMS[name]
            if parm.required:
                required_str = \
                    "Required."
            else:
                required_str = \
                    "Optional, with default: {}". \
                    format(parm.default)
            if parm.example:
                example_str = "\n  Example: {}".format(parm.example)
            else:
                example_str = ""
            desc_str = parm.desc.strip(' \n') + '\n' + required_str
            desc_str = indent(desc_str, 2)
            print("\n* {} ({}):\n{}{}".
                  format(name, parm.type, desc_str, example_str))
        print("")
        sys.exit(2)


class HelpConfigFileAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The config file is in YAML format and contains zero or more config parameters.

Here is an example config file, with all supported config parameters and their
definitions as YAML comments:

---
# Example {} config file
""".format(CMD_NAME))
        for name in CONFIG_PARMS:
            parm = CONFIG_PARMS[name]
            desc_str = parm.desc.strip(' \n')
            desc_str = indent(desc_str, 1, '# ')
            print(desc_str)
            example_value = parm.example or parm.default
            yaml_str = yaml.dump({name: example_value})
            print(yaml_str)
        sys.exit(2)


class HelpOutputFormatAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The output format for each log entry is defined in the 'format' config
parameter using a Python new-style format string, using predefined names for
the fields of the log entry.

The fields can be arbitrarily selected and ordered in the format string, and
the complete syntax for replacement fields in new-style format strings can be
used to determine for example adjustment, padding or conversion.

Example for use in a config file:

    format: '{time:32} {label} {type:8} {name:12} {id:>4} {user:20} {msg}'

Example for using a command line option:

    --format '{time:32} {label} {type:8} {name:12} {id:>4} {user:20} {msg}'

The format string shown in the examples is also the default.

Supported fields:

* time: The time stamp of the log entry, as reported by the HMC in the log
  entry data. This is the time stamp that is also shown in the HMC GUI.
  The format of this field is defined in the 'time_format' config parameter.
  Invoke with --help-time-format for details.

* label: The label for the HMC that was specified in the 'label' config
  parameter.

* type: The log type to which this log entry belongs: Security, Audit.

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
""")
        sys.exit(2)


class HelpTimeFormatAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The format for the 'time' field in the output for each log entry is defined in
the 'time_format' config parameter using a Python datetime.strftime() format
string, or alternatively some keywords:

- iso8601: ISO 8601 format with 'T' as delimiter,
  e.g. 2019-08-09T12:46:38.550000+02:00
- iso8601b: ISO 8601 format with ' ' as delimiter,
  e.g. 2019-08-09 12:46:38.550000+02:00
- Any other value is interpreted as datetime.strftime() format string.

Example for use in a config file:

    time_format: '%Y-%m-%d %H:%M:%S.%f%z'

Example for using a command line option:

    --time_format '%Y-%m-%d %H:%M:%S.%f%z'

The format for the 'asctime' field in any self-log messages is defined in the
'selflog_time_format' config parameter also using a Python datetime.strftime()
format string.

The syntax for datetime.strftime() format strings is described here:
https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior

The datetime objects used for these time stamps are timezone-aware, using the
local timezone of the system on which this program runs. Any locale-specific
components in the datetime.strftime() format string are created using the
locale of the system on which this program runs (e.g. the name of weekdays).
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
        "The log entries can be selected based on log type (security / audit) "
        "and time range, and will be sent to a destination such as stdout, "
        "or the local or remote system log (used for QRadar). "
        "It is possible to wait in a loop for future log entries to be "
        "created.",
        usage="{} [options]".format(CMD_NAME),
        epilog="Invoke with --help-config to see the optionality and defaults "
        "for config parameters.")

    general_opts = parser.add_argument_group('General options')
    general_opts.add_argument(
        '-h', '--help',
        action='help', default=argparse.SUPPRESS,
        help="Show this help message and exit.")
    general_opts.add_argument(
        '--help-config',
        action=HelpConfigAction, nargs=0,
        help="Show a help message about the config parameters (including "
        "optionality and defaults) and exit.")
    general_opts.add_argument(
        '--help-config-file',
        action=HelpConfigFileAction, nargs=0,
        help="Show a help message about the config file format and exit.")
    general_opts.add_argument(
        '--help-output-format',
        action=HelpOutputFormatAction, nargs=0,
        help="Show a help message about the output formatting and exit.")
    general_opts.add_argument(
        '--help-time-format',
        action=HelpTimeFormatAction, nargs=0,
        help="Show a help message about the time field formatting and exit.")
    general_opts.add_argument(
        '--version',
        action='version', version='{} {}'.format(CMD_NAME, __version__),
        help="Show the version number of this program and exit.")
    general_opts.add_argument(
        '--debug',
        dest='debug', action='store_true',
        help="Show debug self-log messages (if any).")

    # Note: Because the optionality and default values are defined in the
    # CONFIG_PARMS variable, the argument definitions here must all define
    # required=False, default=None (both being default for add_argument(),
    # except for store_true/false actions).
    config_opts = parser.add_argument_group('Config options')
    config_opts.add_argument(
        '-c', '--config-file', metavar="CONFIGFILE",
        dest='config_file', action='store',
        help="File path of the config file to use. Default: No config file.")
    config_opts.add_argument(
        "--hmc_host",
        dest='hmc_host', metavar='HOST', action='store',
        help="{}\nOverrides the 'hmc_host' parameter from the config file.".
        format(CONFIG_PARMS['hmc_host'].desc))
    config_opts.add_argument(
        "--hmc_user",
        dest='hmc_user', metavar='USER', action='store',
        help="{}\nOverrides the 'hmc_user' parameter from the config file.".
        format(CONFIG_PARMS['hmc_user'].desc))
    config_opts.add_argument(
        "--hmc_password",
        dest='hmc_password', metavar='PASSWORD', action='store',
        help="{}\nOverrides the 'hmc_password' parameter from the config "
        "file.".
        format(CONFIG_PARMS['hmc_password'].desc))
    config_opts.add_argument(
        "--label",
        dest='label', metavar='LABEL', action='store',
        help="{}\nOverrides the 'label' parameter from the config file.".
        format(CONFIG_PARMS['label'].desc))
    config_opts.add_argument(
        '--log',
        dest='logs', metavar='LOG', action='append',
        help="{}\nEach occurrence adds a log. Overrides the 'logs' parameter "
        "from the config file.".
        format(CONFIG_PARMS['logs'].desc))
    config_opts.add_argument(
        '--since',
        dest='since', metavar='SINCE', action='store',
        help="{}\nOverrides the 'since' parameter from the config file.".
        format(CONFIG_PARMS['since'].desc))
    config_opts.add_argument(
        '--future',
        dest='future', action='store_true', default=None,
        help="{}\nOverrides the 'future' parameter from the config file.".
        format(CONFIG_PARMS['future'].desc))
    config_opts.add_argument(
        '--no-future',
        dest='future', action='store_false', default=None,
        help="Do not wait for future log entries.\n"
        "Overrides the 'future' parameter from the config file.")
    config_opts.add_argument(
        '--dest',
        dest='dest', metavar='DEST', action='store',
        help="{}\nOverrides the 'dest' parameter from the config file.".
        format(CONFIG_PARMS['dest'].desc))
    config_opts.add_argument(
        '--syslog_host',
        dest='syslog_host', metavar='HOST', action='store',
        help="{}\nOverrides the 'syslog_host' parameter from the config file.".
        format(CONFIG_PARMS['syslog_host'].desc))
    config_opts.add_argument(
        '--syslog_port',
        dest='syslog_port', metavar='PORT', action='store',
        help="{}\nOverrides the 'syslog_port' parameter from the config file.".
        format(CONFIG_PARMS['syslog_port'].desc))
    config_opts.add_argument(
        '--syslog_porttype',
        dest='syslog_porttype', metavar='PORTTYPE', action='store',
        help="{}\nOverrides the 'syslog_porttype' parameter from the config "
        "file.".
        format(CONFIG_PARMS['syslog_porttype'].desc))
    config_opts.add_argument(
        '--syslog_facility',
        dest='syslog_facility', metavar='FACILITY', action='store',
        help="{}\nOverrides the 'syslog_facility' parameter from the config "
        "file.".
        format(CONFIG_PARMS['syslog_facility'].desc))
    config_opts.add_argument(
        '--format',
        dest='format', action='store',
        help="{}\nOverrides the 'format' parameter from the config file.".
        format(CONFIG_PARMS['format'].desc))
    config_opts.add_argument(
        '--time_format',
        dest='time_format', action='store',
        help="{}\nOverrides the 'time_format' parameter from the config file.".
        format(CONFIG_PARMS['time_format'].desc))

    args = parser.parse_args()
    return args


@attr.attrs
class LogEntry(object):
    """
    Definition of the data maintained for a log entry. This data is independent
    of output formatting.
    """
    time = attr.attrib(type=datetime)  # time stamp as datetime object
    label = attr.attrib(type=str)  # HMC label
    type = attr.attrib(type=str)  # type (Security, Audit)
    name = attr.attrib(type=str)  # name of the log entry
    id = attr.attrib(type=int)  # ID of the log entry
    user = attr.attrib(type=str)  # HMC userid associated with log entry
    msg = attr.attrib(type=str)  # Formatted message
    msg_vars = attr.attrib(type=list)  # List of subst.vars in message
    detail_msgs = attr.attrib(type=list)  # List of formatted detail messages
    detail_msgs_vars = attr.attrib(type=list)  # List of list of subst.vars


class OutputHandler(object):
    """
    Handle the outputting of any log entries to the defined destination.
    """

    def __init__(self, config):
        """
        Parameters:

          config (Config): The configuration for the program.
        """
        self.config = config
        self.logger = None
        label_hdr = 'Label'
        label = self.config.get_parm('label') or ''
        self.label_len = max(len(label_hdr), len(label))
        self.label_hdr = label_hdr.ljust(self.label_len)
        self.label = label.ljust(self.label_len)
        self.time_format = self.config.get_parm('time_format')

        # Check validity of the format string:
        format = self.config.get_parm('format')
        try:
            format.format(
                time='test', label='test', type='test', name='test', id='test',
                user='test', msg='test', msg_vars='test',
                detail_msgs='test', detail_msgs_vars='test')
        except KeyError as exc:
            # KeyError is raised when the format string contains a named
            # placeholder that is not provided in format().
            raise UserError(
                "Config parameter 'format' specifies an invalid field: {}".
                format(str(exc)))

        # Check validity of the time_format string:
        dt = datetime.now()
        try:
            self.formatted_time(dt)
        except UnicodeError as exc:
            raise UserError(
                "Config parameter 'time_format' is invalid: {}".
                format(str(exc)))

    def formatted_time(self, dt):
        if self.time_format == 'iso8601':
            return dt.isoformat()
        if self.time_format == 'iso8601b':
            return dt.isoformat(' ')
        return dt.strftime(self.time_format)  # already checked in __init__()

    def output_begin(self):
        dest = self.config.get_parm('dest')
        format = self.config.get_parm('format')
        if dest == 'stdout':
            out_str = format.format(
                time='Time', label=self.label_hdr, type='Type', name='Name',
                id='ID', user='Userid', msg='Message',
                msg_vars='Message variables', detail_msgs='Detail messages',
                detail_msgs_vars='Detail messages variables')
            print(out_str)
            print("-" * 120)
            sys.stdout.flush()
        else:
            assert dest == 'syslog'
            self.syslog_host = self.config.get_parm('syslog_host')
            self.syslog_port = self.config.get_parm('syslog_port')
            self.syslog_facility = self.config.get_parm('syslog_facility')
            assert self.syslog_facility in SysLogHandler.facility_names
            facility_code = SysLogHandler.facility_names[self.syslog_facility]
            self.syslog_porttype = self.config.get_parm('syslog_porttype')
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
        dest = self.config.get_parm('dest')
        if dest == 'stdout':
            print("-" * 120)
            sys.stdout.flush()
        else:
            assert dest == 'syslog'
            pass  # nothing to do

    def output_entries(self, log_entries):
        table = list()
        for le in log_entries:
            hmc_time = le['event-time']
            le_time = zhmcclient.datetime_from_timestamp(
                hmc_time, tz.tzlocal())
            le_type = le['log-type']
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
                time=le_time, label=self.label, type=le_type, name=le_name,
                id=le_id, user=le_user, msg=le_msg, msg_vars=le_msg_vars,
                detail_msgs=le_detail_msgs,
                detail_msgs_vars=le_detail_msgs_vars)
            table.append(row)
        sorted_table = sorted(table, key=lambda row: row.time)
        dest = self.config.get_parm('dest')
        format = self.config.get_parm('format')
        if dest == 'stdout':
            for row in sorted_table:
                out_str = format.format(
                    time=self.formatted_time(row.time), label=row.label,
                    type=row.type, name=row.name, id=row.id, user=row.user,
                    msg=row.msg, msg_vars=row.msg_vars,
                    detail_msgs=row.detail_msgs,
                    detail_msgs_vars=row.detail_msgs_vars)
                print(out_str)
            sys.stdout.flush()
        else:
            assert dest == 'syslog'
            for row in sorted_table:
                out_str = format.format(
                    time=self.formatted_time(row.time), label=row.label,
                    type=row.type, name=row.name, id=row.id, user=row.user,
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
            dt = dt.replace(tzinfo=tz.tzlocal())
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

    def __init__(self, config, debug):
        """
        Parameters:

          config (Config): The configuration for the program.

          debug (bool): Show debug self-log messages. This causes causes the
            log level to be increased from INFO to DEBUG.
        """
        self._config = config
        self._debug = debug
        self._logger = None  # Lazy initialization

    def _setup(self):
        """
        Set up the logger, if not yet set up.
        """
        if self._logger is None:
            dest_str = self._config.get_parm('selflog_dest')
            if dest_str == 'stdout':
                dest = sys.stdout
            else:
                assert dest_str == 'stderr'
                dest = sys.stderr
            format = self._config.get_parm('selflog_format')
            time_format = self._config.get_parm('selflog_time_format')
            formatter = DatetimeFormatter(fmt=format, datefmt=time_format)
            handler = StreamHandler(dest)
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
            e['log-type'] = 'Audit'
        log_entries += audit_entries
    if 'security' in logs:
        security_entries = console.get_security_log(begin_time, end_time)
        for e in security_entries:
            e['log-type'] = 'Security'
        log_entries += security_entries
    return log_entries


def main():
    """
    Main routine of the script.
    """

    requests.packages.urllib3.disable_warnings()  # Used by zhmcclient

    try:  # transform any of our exceptions to an error exit

        args = parse_args()

        config = Config()
        if args.config_file:
            config.update_from_file(args.config_file)
        config.update_from_args(args)

        SELF_LOGGER = SelfLogger(config, args.debug)

        hmc = config.get_parm('hmc_host')
        userid = config.get_parm('hmc_user')
        password = config.get_parm('hmc_password')
        label = config.get_parm('label')
        dest = config.get_parm('dest')
        logs = config.get_parm('logs')
        since = config.get_parm('since')
        future = config.get_parm('future')
        syslog_host = config.get_parm('syslog_host')
        syslog_port = config.get_parm('syslog_port')
        syslog_porttype = config.get_parm('syslog_porttype')
        syslog_facility = config.get_parm('syslog_facility')

        if since == 'all':
            begin_time = None
            since_str = 'all'
        elif since == 'now':
            begin_time = datetime.now(tz.tzlocal())
            since_str = 'now ({})'.format(begin_time)
        else:
            assert since is not None
            try:
                begin_time = parser.parse(since)
                # TODO: Pass tzinfos arg; by default, only UTC is supported.
                if begin_time.tzinfo is None:
                    begin_time = begin_time.replace(tzinfo=tz.tzlocal())
                since_str = '{}'.format(begin_time)
            except (ValueError, OverflowError) as exc:
                raise UserError(
                    "Config parameter 'since' has an invalid date & time "
                    "value: {}".
                    format(args.since))

        out_handler = OutputHandler(config)  # Checks validity of format
        if dest == 'stdout':
            dest_str = dest
        else:
            assert dest == 'syslog'
            dest_str = "{} (server {}, port {}/{}, facility {})". \
                format(dest, syslog_host, syslog_port, syslog_porttype,
                       syslog_facility)

        SELF_LOGGER.info(
            "{} starting".format(CMD_NAME))
        SELF_LOGGER.info(
            "{} version: {}".format(CMD_NAME, __version__))
        SELF_LOGGER.info(
            "HMC: {host}, Userid: {user}, Label: {label}".
            format(host=hmc, user=userid, label=label))
        SELF_LOGGER.info(
            "Logs: {logs}, Since: {since}, Future: {future}".
            format(logs=', '.join(logs), since=since_str, future=future))
        SELF_LOGGER.info(
            "Destination: {dest}".
            format(dest=dest_str))

        try:  # make sure the session gets logged off

            session = zhmcclient.Session(hmc, userid, password)
            client = zhmcclient.Client(session)
            console = client.consoles.console

            out_handler.output_begin()

            log_entries = get_log_entries(
                logs, console, begin_time=begin_time, end_time=None)
            out_handler.output_entries(log_entries)

            if future:
                topic_items = session.get_notification_topics()
                security_topic_name = None
                audit_topic_name = None
                topic_names = list()
                for topic_item in topic_items:
                    topic_type = topic_item['topic-type']
                    if topic_type == 'security-notification' \
                            and 'security' in logs:
                        security_topic_name = topic_item['topic-name']
                        topic_names.append(security_topic_name)
                    if topic_type == 'audit-notification' \
                            and 'audit' in logs:
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
                                            le['log-type'] = 'Security'
                                        out_handler.output_entries(log_entries)
                                    elif topic_name == audit_topic_name:
                                        log_entries = message['log-entries']
                                        for le in log_entries:
                                            le['log-type'] = 'Audit'
                                        out_handler.output_entries(log_entries)
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
