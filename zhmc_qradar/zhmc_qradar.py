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
import logging
import argparse
import yaml
import requests.packages.urllib3
from datetime import datetime
from dateutil import parser
from dateutil.tz import tzlocal
import zhmcclient


class Error(Exception):
    pass


class UserError(Error):
    pass


def load_config(filepath):
    """
    Load the zhmc_qradar config file and return a dict with config parms.
    """
    try:
        with open(filepath, 'r') as fp:
            config = yaml.safe_load(fp)
    except IOError as exc:
        raise UserError(
            "Cannot load zhmc_qradar config file {}: {}".
            format(filepath, exc))
    return config


def get_optional_config_parm(config, name, default=None):
    return config.get(name, default)


def get_required_config_parm(config, name):
    try:
        return config[name]
    except KeyValue:
        raise UserError(
            "Config file does not contain required parameter '{}'".
            format(name))


def parse_args():
    """
    Create and configure an argument parser using the Python argparse module
    and parse the command line arguments.

    Returns:
        argparse.Namespace: Dictionary with parsing results.
    """
    default_config_file = '~/.zhmc_qradar.config.yml'
    parser = argparse.ArgumentParser(
        description="QRadar support for the IBM Z HMC, written in pure Python")
    parser.add_argument(
        "-c", "--config-file", metavar="CONFIGFILE",
        dest='config_file', action='store',
        required=False, default=default_config_file,
        help="File path of zhmc_qradar config file to use. "
            "Default: {}".format(default_config_file))
    parser.add_argument(
        "-s", "--since",
        dest='since', action='store',
        required=False, default='start',
        help="Include past log entries since the specified date and time "
            "If no timezone is specified, the local timezone is assumed. "
            "Special values: 'start' will include all available past log "
            "entries; 'now' means the current time. "
            "Default: start.")
    parser.add_argument(
        "-f", "--future",
        dest='future', action='store_true',
        required=False, default=False,
        help="Wait for future log entries. Use keyboard interrupt to leave."
            "Default: Do not wait for future log entries.")
    args = parser.parse_args()
    return args


class OutputHandler(object):

    def __init__(self, dest):
        self.dest = dest
        self.stdout_format_str = \
            "{type:8}  {time:32}  {name:12}  {id:>4}  {user:20}  {msg}"

    def output_begin(self):
        out_str = self.stdout_format_str.format(
            type='Type', time='Time', name='Event name', id='ID',
            user='Userid', msg='Message')
        print(out_str)
        sys.stdout.flush()

    def output_end(self):
        pass

    def output_entries(self, log_entries):
        if self.dest == 'stdout':
            table = list()
            for le in log_entries:
                le_type = le['log-type']
                hmc_time = le['event-time']
                le_time = zhmcclient.datetime_from_timestamp(
                    hmc_time, tzlocal())
                le_name = le['event-name']
                le_id = le['event-id']
                le_user = le['userid']
                le_msg = le['event-message']
                row = [le_type, le_time, le_name, le_id, le_user, le_msg]
                table.append(row)
            sort_row_index = 1  # time column
            sorted_table = sorted(table, key=lambda row: row[sort_row_index])
            for row in sorted_table:
                out_str = self.stdout_format_str.format(
                    type=row[0], time=str(row[1]), name=row[2], id=row[3],
                    user=row[4] or '', msg=row[5])
                print(out_str)
            sys.stdout.flush()
        elif self.dest == 'qradar':
            # TODO: Implement
            raise NotImplementedError


def get_log_entries(logs, console, begin_time, end_time):
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

    try:
        args = parse_args()

        config = load_config(args.config_file)

        hmc = get_required_config_parm(config, 'hmc_host')
        userid = get_required_config_parm(config, 'hmc_user')
        password = get_required_config_parm(config, 'hmc_password')
        dest = get_optional_config_parm(config, 'dest', 'stdout')

        permitted_dests = ['stdout']
        if dest not in permitted_dests:
            raise UserError(
                "Config file {} contains parameter '{}' with invalid value: {} "
                "(permitted values are: {})".
                format(args.config_file, 'dest', dest,
                       ', '.join(permitted_dests)))

        permitted_logs = ['security', 'audit']
        logs = get_optional_config_parm(config, 'logs', ['security', 'audit'])
        if not all(log in permitted_logs for log in logs):
            raise UserError(
                "Config file {} contains parameter '{}' with invalid value: {} "
                "(permitted is a list of zero or more of the following "
                "values: {})".
                format(args.config_file, 'logs', logs,
                       ', '.join(permitted_logs)))

        if args.since == 'start':
            begin_time = None
            since_str = 'start'
        elif args.since == 'now':
            begin_time = datetime.now(tzlocal())
            since_str = 'now ({})'.format(begin_time)
        else:
            try:
                begin_time = parser.parse(args.since)
                # TODO: Pass tzinfos argument. By default, only UTC is supported
                if begin_time.tzinfo is None:
                    begin_time = begin_time.replace(tzinfo=tzlocal())
                since_str = '{}'.format(begin_time)
            except (ValueError, OverflowError) as exc:
                raise UserError(
                    "Option -s/--since has an invalid date & time value: {}".
                    format(args.since))

        print("Using HMC {} with userid {} ...".
              format(hmc, userid))
        print("Log destination:                 {}".
              format(dest))
        print("Gathering these HMC logs:        {}".
              format(', '.join(logs)))
        print("Include log entries since:       {}".
              format(since_str))
        print("Wait for future log entries:     {}".
              format('yes' if args.future else 'no'))
        print("")
        sys.stdout.flush()

        session = zhmcclient.Session(hmc, userid, password)
        client = zhmcclient.Client(session)
        console = client.consoles.console

        out_handler = OutputHandler(dest)
        out_handler.output_begin()

        log_entries = get_log_entries(
            logs, console, begin_time=begin_time, end_time=None)
        out_handler.output_entries(log_entries)

        if args.future:
            # TODO: Create topic for log entries. It seems that the zhmcclient
            # does not provide functionality for that, yet.
            topic = 'dummy'
            receiver = zhmcclient.NotificationReceiver(
                topic, hmc, userid, password)
            try:
                for headers, message in receiver.notifications():
                    # TODO: Process notification
                    print("Debug: notification:\n"
                          "  headers={!r}\n"
                          "  message={!r}".format(headers, message))
                    sys.stdout.flush()
                log_entries = []
                # TODO: Get log entries since last time
                out_handler.output_entries(log_entries)
            except KeyboardInterrupt:
                print("Keyboard interrupt - leaving receiver loop")
                sys.stdout.flush()
            finally:
                print("Closing receiver...")
                sys.stdout.flush()
                receiver.close()

        out_handler.output_end()

        print("Logging off...")
        sys.stdout.flush()
        session.logoff()

    except Error as exc:
        print("zhmc_qradar: error: {}".format(exc))
        sys.exit(1)


if __name__ == '__main__':
    main()
