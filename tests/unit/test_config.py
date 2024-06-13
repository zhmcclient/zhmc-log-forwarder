#!/usr/bin/env python
"""Unit tests for zhmc_log_forwarder.Config class"""

import os
import uuid
import pytest

from zhmc_log_forwarder import zhmc_log_forwarder

# Prefix for any created resources
TEST_PREFIX = 'zhmc_log_forwarder_config'


TESTCASES_CONFIG_LOAD = [
    #
    # desc (str): Testcase description
    # config_file (str): Content of config file to be loaded.
    # exp_parms (dict): Expected config file parameters, if success.
    # exp_exc (exc class): Expected exception class, if failure.
    (
        "Empty config file",
        "",
        {},
        zhmc_log_forwarder.UserError
    ),
    (
        "Config file with minimal properties",
        """
hmc_host: 10.11.12.13
hmc_user: user1
hmc_password: pw1
stomp_retry_timeout_config: {}
""",
        {
            "hmc_host": "10.11.12.13",
            "hmc_user": "user1",
            "hmc_password": "pw1",
            "hmc_verify_cert": True,
            "stomp_retry_timeout_config": {},
            # Default items:
            'check_data': {'functional_users': [], 'imgmt_subnet': None},
            'forwardings': [],
            'future': False,
            'label': None,
            'log_message_file': None,
            'selflog_dest': 'stdout',
            'selflog_format': '%(levelname)s: %(message)s',
            'selflog_time_format': '%Y-%m-%d %H:%M:%S.%f%z',
        },
        None
    ),
]


@pytest.mark.parametrize(
    "desc, config_file, exp_parms, exp_exc", TESTCASES_CONFIG_LOAD
)
def test_config_load(desc, config_file, exp_parms, exp_exc):
    # pylint: disable=unused-argument
    """Tests if some generic file is correctly parsed."""

    config_filename = "{}_{}.yaml".format(TEST_PREFIX, uuid.uuid4().hex)
    with open(config_filename, "w+", encoding='utf-8') as cf:
        cf.write(config_file)

    try:
        config = zhmc_log_forwarder.Config()
        if exp_exc:
            with pytest.raises(exp_exc):

                config.load_config_file(config_filename)

        else:

            config.load_config_file(config_filename)

            assert config.parms == exp_parms
    finally:
        os.remove(config_filename)
