from logging import getLogger
from typing import Callable

import pytest

from logprep.factory import Factory
from logprep.processor.base.rule import Rule


class ExceptionBaseTest:
    exception: Callable
    """Class of exception to test"""

    error_message: str
    """regex string to match the error message"""

    counted_metric_name: str
    """name of the metric that should be counted"""

    def setup_method(self):
        self.processor = Factory.create(
            {"my_dissector": {"type": "dissector", "specific_rules": [], "generic_rules": []}},
            getLogger(),
        )
        self.rule = Rule._create_from_dict({"filter": "message", "rule": {}})
        self.event = {"message": "test_event"}
        self.exception_args = ("the error message", self.rule, self.event)

    def test_error_message(self):
        with pytest.raises(self.exception, match=self.error_message):
            raise self.exception(*self.exception_args)

    def test_metrics_counts(self):
        setattr(self.rule.metrics, self.counted_metric_name, 0)
        self.rule.metrics.number_of_warnings = 0
        with pytest.raises(self.exception):
            raise self.exception(*self.exception_args)
        assert getattr(self.rule.metrics, self.counted_metric_name) == 1
