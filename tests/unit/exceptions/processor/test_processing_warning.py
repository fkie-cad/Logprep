# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long
from logging import getLogger
from typing import Callable

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
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


class TestProcessingWarning(ExceptionBaseTest):
    exception = ProcessingWarning

    error_message = (
        r"ProcessingWarning: the error message, Rule: rule.id='.*',"
        r" rule.description='', event=\{'message': 'test_event'\}"
    )

    counted_metric_name = "number_of_warnings"


class TestFieldExsitsWarning(ExceptionBaseTest):
    exception = FieldExistsWarning
    error_message = (
        r"FieldExistsWarning: The following fields could not be written,"
        r" because one or more subfields existed and could not be extended: "
        r"my_field, Rule: rule.id='.*', rule.description='', event=\{'message': 'test_event'\}"
    )

    counted_metric_name = "number_of_warnings"

    def setup_method(self):
        super().setup_method()
        self.exception_args = (self.rule, self.event, ["my_field"])
