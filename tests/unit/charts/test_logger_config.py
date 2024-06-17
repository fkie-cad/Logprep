# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest


class TestLoggerConfig(TestBaseChartTest):

    def test_logger_config_is_populated(self):
        assert False
