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
QRadar support for the IBM Z HMC, written in pure Python
"""

import sys
import argparse
import warnings
from datetime import datetime
from collections import OrderedDict
import textwrap

import attr
import pbr
import yaml
import requests.packages.urllib3
from dateutil import parser, tz

import zhmcclient

__version__ = pbr.version.VersionInfo('zhmc-qradar').release_string()

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
    example_yaml = attr.attrib(type=str, default=None)  # example for file


# Definition of all configuration parameters for this script.
CONFIG_PARMS = OrderedDict()
CONFIG_PARMS['hmc_host'] = ConfigParm(
    type='string', example_yaml="'10.11.12.13'",
    required=True,
    desc="IP address or hostname of the HMC.")
CONFIG_PARMS['hmc_user'] = ConfigParm(
    type='string', example_yaml="myuser",
    required=True,
    desc="HMC userid.")
CONFIG_PARMS['hmc_password'] = ConfigParm(
    type='string', example_yaml="mypassword",
    required=True,
    desc="HMC password.")
CONFIG_PARMS['dest'] = ConfigParm(
    type='string', example_yaml="stdout",
    allowed=['stdout'],
    required=False, default='stdout',
    desc="""
Destination for the log entries:
- 'stdout': Standard output.
""")
CONFIG_PARMS['logs'] = ConfigParm(
    type='list/tuple of string', example_yaml="[security, audit]",
    allowed=['security', 'audit'],
    required=False, default=['security', 'audit'],
    desc="""
List of log types to include, with the following list item values:
- 'security': HMC Security Log."
- 'audit': HMC Audit Log.
""")
CONFIG_PARMS['since'] = ConfigParm(
    type='string', example_yaml="now",
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
    type='bool', example_yaml="false",
    required=False, default=False,
    desc="""
Wait for future log entries. Use keyboard interrupt (e.g. Ctrl-C) to stop the
program.
""")
CONFIG_PARMS['format'] = ConfigParm(
    type='string',
    example_yaml="'{type:8}  {time:32}  {name:12}  {id:>4}  {user:20}  {msg}'",
    required=False,
    default='{type:8}  {time:32}  {name:12}  {id:>4}  {user:20}  {msg}',
    desc="""
Format of the output for each log entry. See --help-format for details.
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
        repr_str = "Config({})".format(self.parms)
        return repr_str

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
            desc_str = parm.desc.strip(' \n') + '\n' + required_str
            desc_str = indent(desc_str, 2)
            print("\n* {} ({}):\n{}".
                  format(name, parm.type, desc_str))
        print("")
        sys.exit(2)


class HelpConfigFileAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The config file is in YAML format and contains zero or more of the
config parameters explained in the --help-config option.

Here is an example config file:

---
# Example zhmc_qradar config file""")
        for name in CONFIG_PARMS:
            parm = CONFIG_PARMS[name]
            desc_str = parm.desc.strip(' \n')
            desc_str = indent(desc_str, 1, '# ')
            print("\n{}\n{}: {}".
                  format(desc_str, name, parm.example_yaml, desc_str))
        print("")
        sys.exit(2)


class HelpOutputFormatAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        print("""
The output format for each log entry is defined using a new-style Python
string format, using predefined names for the fields of the log entry.

The fields can be arbitrarily selected and ordered in the format string,
and all modifiers supported by Python can be used to determine things like
adjustment, padding or truncation.

Example (in YAML config file):

    format: '{type:8}  {time:32}  {name:12}  {id:>4}  {user:20}  {msg}'

Supported fields:

* type: The log type: Security, Audit.

* time: The time stamp of the log entry in the standard format for Python
  datetime objects, e.g. 2019-08-07 05:56:37.177189+02:00.

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


def parse_args():
    """
    Create and configure an argument parser using the Python argparse module
    and parse the command line arguments.

    Returns:
        argparse.Namespace: Dictionary with parsing results.
    """
    parser = argparse.ArgumentParser(
        add_help=False,
        description="Collector for security and audit logs from an IBM Z HMC. "
        "The log entries can be selected based on log type and time range, "
        "and will be sent to a destination such as stdout or a QRadar "
        "service.",
        usage="zhmc_qradar [options]",
        epilog="")

    general_opts = parser.add_argument_group('General options')
    general_opts.add_argument(
        '-h', '--help',
        action='help', default=argparse.SUPPRESS,
        help="Show this help message and exit.")
    general_opts.add_argument(
        '--help-config',
        action=HelpConfigAction, nargs=0,
        help="Show a help message about the config parameters and exit.")
    general_opts.add_argument(
        '--help-config-file',
        action=HelpConfigFileAction, nargs=0,
        help="Show a help message about the config file format and exit.")
    general_opts.add_argument(
        '--help-output-format',
        action=HelpOutputFormatAction, nargs=0,
        help="Show a help message about the output formatting and exit.")
    general_opts.add_argument(
        '--version',
        action='version', version='zhmc_qradar {}'.format(__version__),
        help="Show the version number of this program and exit.")

    config_opts = parser.add_argument_group('Config options')
    config_opts.add_argument(
        '-c', '--config-file', metavar="CONFIGFILE",
        dest='config_file', action='store',
        required=False, default=None,
        help="File path of the config file to use. Default: No config file.")
    config_opts.add_argument(
        "--hmc_host",
        dest='hmc_host', metavar='HOST', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'hmc_host' parameter from the config file.".
        format(CONFIG_PARMS['hmc_host'].desc))
    config_opts.add_argument(
        "--hmc_user",
        dest='hmc_user', metavar='USER', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'hmc_user' parameter from the config file.".
        format(CONFIG_PARMS['hmc_user'].desc))
    config_opts.add_argument(
        "--hmc_password",
        dest='hmc_password', metavar='PASSWORD', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'hmc_password' parameter from the config "
        "file.".
        format(CONFIG_PARMS['hmc_password'].desc))
    config_opts.add_argument(
        '--dest',
        dest='dest', metavar='DEST', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'dest' parameter from the config file.".
        format(CONFIG_PARMS['dest'].desc))
    config_opts.add_argument(
        '--log',
        dest='logs', metavar='LOG', action='append',
        required=False, default=None,
        help="{}\nEach occurrence adds a log. Overrides the 'logs' parameter "
        "from the config file.".
        format(CONFIG_PARMS['logs'].desc))
    config_opts.add_argument(
        '--since',
        dest='since', metavar='SINCE', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'since' parameter from the config file.".
        format(CONFIG_PARMS['since'].desc))
    config_opts.add_argument(
        '--future',
        dest='future', action='store_true',
        required=False, default=None,
        help="{}\nOverrides the 'future' parameter from the config file.".
        format(CONFIG_PARMS['future'].desc))
    config_opts.add_argument(
        '--no-future',
        dest='future', action='store_false',
        required=False, default=None,
        help="Do not wait for future log entries.\n"
        "Overrides the 'future' parameter from the config file.")
    config_opts.add_argument(
        '--format',
        dest='format', action='store',
        required=False, default=None,
        help="{}\nOverrides the 'format' parameter from the config file.".
        format(CONFIG_PARMS['format'].desc))

    args = parser.parse_args()
    return args


@attr.attrs
class LogEntry(object):
    """
    Definition of the data maintained for a log entry. This data is independent
    of output formatting.
    """
    type = attr.attrib(type=str)  # type (Security, Audit)
    time = attr.attrib(type=str)  # time stamp in Python datetime output format
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

    def __init__(self, dest, format):
        self.dest = dest
        self.stdout_format_str = format

        # Check validity of the format string:
        try:
            self.stdout_format_str.format(
                type='Type', time='Time', name='Event name', id='ID',
                user='Userid', msg='Message', msg_vars='Message variables',
                detail_msgs='Detail messages',
                detail_msgs_vars='Detail messages variables')
        except KeyError as exc:
            # KeyError is raised when the format string contains a named
            # placeholder that is not provided in format().
            raise UserError(
                "Config parameter 'format' specifies an invalid field: {}".
                format(str(exc)))

    def output_begin(self):
        out_str = self.stdout_format_str.format(
            type='Type', time='Time', name='Event name', id='ID',
            user='Userid', msg='Message', msg_vars='Message variables',
            detail_msgs='Detail messages',
            detail_msgs_vars='Detail messages variables')
        print(out_str)
        print("-" * 120)
        sys.stdout.flush()

    def output_end(self):
        print("-" * 120)
        sys.stdout.flush()

    def output_entries(self, log_entries):
        if self.dest == 'stdout':
            table = list()
            for le in log_entries:
                le_type = le['log-type']
                hmc_time = le['event-time']
                le_time = zhmcclient.datetime_from_timestamp(
                    hmc_time, tz.tzlocal())
                le_name = le['event-name']
                le_id = le['event-id']
                le_user = le['userid'] or ''
                le_msg = le['event-message']
                data_items = le['event-data-items']
                data_items = sorted(data_items, key=lambda i: i['data-item-number'])
                le_msg_vars = [(i['data-item-value'], i['data-item-type'])
                               for i in data_items]
                le_detail_msgs = []
                le_detail_msgs_vars = []
                row = LogEntry(
                    type=le_type, time=le_time, name=le_name, id=le_id,
                    user=le_user, msg=le_msg, msg_vars=le_msg_vars,
                    detail_msgs=le_detail_msgs,
                    detail_msgs_vars=le_detail_msgs_vars)
                table.append(row)
            sorted_table = sorted(table, key=lambda row: row.time)
            for row in sorted_table:
                out_str = self.stdout_format_str.format(
                    type=row.type, time=str(row.time), name=row.name,
                    id=row.id, user=row.user, msg=row.msg,
                    msg_vars=row.msg_vars)
                print(out_str)
            sys.stdout.flush()
        elif self.dest == 'qradar':
            # TODO: Implement
            raise NotImplementedError


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

    requests.packages.urllib3.disable_warnings()

    try:  # transform any of our exceptions to an error exit

        args = parse_args()

        config = Config()
        if args.config_file:
            config.update_from_file(args.config_file)
        config.update_from_args(args)

        hmc = config.get_parm('hmc_host')
        userid = config.get_parm('hmc_user')
        password = config.get_parm('hmc_password')
        dest = config.get_parm('dest')
        logs = config.get_parm('logs')
        since = config.get_parm('since')
        future = config.get_parm('future')
        format = config.get_parm('format')

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

        out_handler = OutputHandler(dest, format)  # Checks validity of format

        print("Collector for security and audit logs from an IBM Z HMC.")
        print("")
        print("HMC address:                     {}".format(hmc))
        print("HMC userid:                      {}".format(userid))
        print("Log destination:                 {}".format(dest))
        print("Gathering these HMC logs:        {}".format(', '.join(logs)))
        print("Include log entries since:       {}".format(since_str))
        print("Wait for future log entries:     {}".format(
            'yes (use keyboard interrupt to stop, e.g. Ctrl-C)'
            if future else 'no'))
        print("")
        sys.stdout.flush()

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
                        print("Waiting for future log entries")
                        sys.stdout.flush()
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
                                        warnings.warn(
                                            "Ignoring invalid topic name: {}".
                                            format(topic_name),
                                            RuntimeWarning)
                                else:
                                    warnings.warn(
                                        "Ignoring invalid notification type: "
                                        "{}".
                                        format(headers['notification-type']),
                                        RuntimeWarning)
                            warnings.warn(
                                "Notification receiver has disconnected - "
                                "reopening",
                                RuntimeWarning)
                    except KeyboardInterrupt:
                        out_handler.output_end()
                        print("Stopping to wait for future log entries")
                        sys.stdout.flush()
                    finally:
                        print("Closing notification receiver")
                        sys.stdout.flush()
                        receiver.close()
            else:
                out_handler.output_end()
        finally:
            print("Logging off")
            sys.stdout.flush()
            session.logoff()
    except Error as exc:
        print("zhmc_qradar: error: {}".format(exc))
        sys.exit(1)


if __name__ == '__main__':
    main()
