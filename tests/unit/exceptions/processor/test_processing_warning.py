# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long
import re
from logging import getLogger

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.processor.base.rule import Rule


class TestProcessingWarning:
    exception = ProcessingWarning

    error_message = """ProcessingWarning in Dissector (my_dissector): the error message
Rule: filename=None, filter="message", Rule.Config(description='', regex_fields=[], tests=[], tag_on_failure=['_rule_failure']),
Event: {'message': 'test_event'}
"""

    def setup_method(self):
        self.processor = Factory.create(
            {"my_dissector": {"type": "dissector", "specific_rules": [], "generic_rules": []}},
            getLogger(),
        )
        self.rule = Rule._create_from_dict({"filter": "message", "rule": {}})
        self.event = {"message": "test_event"}
        self.exception_args = (self.processor, "the error message", self.rule, self.event)

    def test_error_message(self):
        with pytest.raises(self.exception, match=re.escape(self.error_message)):
            raise self.exception(*self.exception_args)

    def test_metrics_counts(self):
        assert self.processor.metrics.number_of_warnings == 0
        with pytest.raises(self.exception, match=re.escape(self.error_message)):
            raise self.exception(*self.exception_args)
        assert self.processor.metrics.number_of_warnings == 1


class TestFieldExsitsWarning(TestProcessingWarning):
    exception = FieldExistsWarning
    error_message = """FieldExistsWarning in Dissector (my_dissector): The following fields could not be written, because one or more subfields existed and could not be extended: my_field
Rule: filename=None, filter="message", Rule.Config(description='', regex_fields=[], tests=[], tag_on_failure=[\'_rule_failure\']),
Event: {'message': 'test_event'}
"""

    def setup_method(self):
        super().setup_method()
        self.exception_args = (self.processor, self.rule, self.event, ["my_field"])
