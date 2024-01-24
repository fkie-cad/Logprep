from logging import getLogger
from unittest import mock

import pytest

from logprep import run_logprep
from logprep.util.configuration import Configuration


class TestQuickstart:
    QUICKSTART_CONFIG_PATH = "quickstart/exampledata/config/pipeline.yml"

    def test_validity_of_quickstart_config(self):
        config = Configuration().create_from_yaml(self.QUICKSTART_CONFIG_PATH)
        config.verify(getLogger("test-logger"))

    def test_quickstart_rules_are_valid(self):
        """ensures the quickstart rules are valid"""
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "verify-config",
                self.QUICKSTART_CONFIG_PATH,
            ],
        ):
            with pytest.raises(SystemExit) as e_info:
                run_logprep.cli()
        assert e_info.value.code == 0
