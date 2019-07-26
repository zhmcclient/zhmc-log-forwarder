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

import argparse
import sys
import logging
import yaml
import requests.packages.urllib3

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
            config = yaml.load(fp)
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
            "Config file does not contain required parameter: {}".
            format(name))


def main():
    """
    Main routine of the script.
    """

    # TODO: Is the following still needed, or done by zhmcclient?
    # requests.packages.urllib3.disable_warnings()

    try:
        parser = argparse.ArgumentParser(
            description="QRadar support for the IBM Z HMC, written in pure Python")
        parser.add_argument(
            "-c", "--config",
            metavar="CONFIGFILE", default="~/.zhmc_qradar.config.yml",
            help="File path of zhmc_qradar config file")
        args = parser.parse_args()

        config = load_config(args.config)

        hmc = get_required_config_parm(config, "hmc_host")
        userid = get_required_config_parm(config, "hmc_user")
        password = get_required_config_parm(config, "hmc_password")
        dest = get_optional_config_parm(config, "dest", 'stdout')

        print("Using HMC {} with userid {} ...".format(hmc, userid))
        session = zhmcclient.Session(hmc, userid, password)
        client = zhmcclient.Client(session)

        # TODO: Create topic for log entries. It seems that the zhmcclient does
        # not provide functionality for that, yet.
        topic = 'dummy'

        receiver = zhmcclient.NotificationReceiver(topic, hmc, userid, password)

        # TODO: Pull the complete log and send to destination

        try:
            for headers, message in receiver.notifications():
                pass

                # TODO: Pull the latest update of log entries, since the last
                # update was pulled, and send to destination

        except KeyboardInterrupt:
            print("Keyboard interrupt - leaving receiver loop")
            sys.stdout.flush()
        finally:
            print("Closing receiver...")
            sys.stdout.flush()
            receiver.close()

        print("Logging off...")
        sys.stdout.flush()
        session.logoff()

    except Error as exc:
        print("Error: {}".format(exc))
        sys.exit(1)

if __name__ == '__main__':
    main()
