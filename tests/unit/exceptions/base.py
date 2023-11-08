# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long
from typing import Callable

import pytest

from logprep.processor.base.rule import Rule


class ExceptionBaseTest:
    exception: Callable
    """Class of exception to test"""

    error_message: str
    """regex string to match the error message"""

    counted_metric_name: str
    """name of the metric attribute as defined in instance class"""

    def setup_method(self):
        self.object = Rule._create_from_dict({"filter": "message", "rule": {}})
        self.event = {"message": "test_event"}
        self.exception_args = ("the error message", self.object, self.event)

    def test_error_message(self):
        with pytest.raises(self.exception, match=self.error_message):
            raise self.exception(*self.exception_args)

    def test_metrics_counts(self):
        setattr(self.object.metrics, self.counted_metric_name, 0)
        with pytest.raises(self.exception):
            raise self.exception(*self.exception_args)
        assert getattr(self.object.metrics, self.counted_metric_name) == 1
