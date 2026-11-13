# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
import re

import pytest

from logprep.abc.processor import Processor
from tests.conftest import ProcessorFailureTestCase, ProcessorTestCase
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    ProcessorTestCase(
        id="split on whitespaces if delimiter not explicitly defined",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "drop_empty": True,
            },
        },
        event={
            "message": "this is the message",
        },
        expected=[
            "this",
            "is",
            "the",
            "message",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times then keep any resulting empty sections",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": False,
            },
        },
        event={
            "message": ",,this,,",
        },
        expected=[
            "",
            "",
            "this",
            "",
            "",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times then drop any resulting empty sections",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": " , ,this, ,",
        },
        expected=[
            "this",
        ],
    ),
]

test_cases = [
    ProcessorTestCase(
        id="split on explicitly defined delimiter",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ", ",
                "drop_empty": True,
            },
        },
        event={
            "message": "this, is, the, message",
        },
        expected=[
            "this",
            "is",
            "the",
            "message",
        ],
    ),
    ProcessorTestCase(
        id="split one item on explicitly defined delimiter",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": "this,",
        },
        expected=[
            "this",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times then drop any resulting empty sections 2",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": ",,this,,",
        },
        expected=[
            "this",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times then drop any resulting empty sections 3",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": ",, this , , ",
        },
        expected=[
            " this ",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times and containing newlines",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": "\n,,this,\t, ",
        },
        expected=[
            "this",
        ],
    ),
    ProcessorTestCase(
        id="split one item containing the delimiter multiple times and containing whitespaces only in front",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": ",, this, , ",
        },
        expected=[
            " this",
        ],
    ),
    ProcessorTestCase(
        id="split containing the delimiter multiple times and whitespaces only in front",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
                "delimiter": ",",
                "drop_empty": True,
            },
        },
        event={
            "message": "hello , world,this, is a very complex,\n , and even multiline, text,,, ",
        },
        expected=[
            "hello ",
            " world",
            "this",
            " is a very complex",
            " and even multiline",
            " text",
        ],
    ),
]

failure_test_cases = [
    ProcessorFailureTestCase(
        id="split something that isn't a string on not explicitly defined delimiter (whitespace)",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "result",
            },
        },
        event={
            "message": [
                "this",
                "is",
                "the",
                "message",
            ],
        },
        expected={
            "message": [
                "this",
                "is",
                "the",
                "message",
            ],
            "tags": [
                "_string_splitter_failure",
            ],
        },
        error_message=".*ProcessingWarning.*",
    ),
    ProcessorFailureTestCase(
        id="split on not explicitly defined delimiter (whitespace) and try to write to existing field",
        rule={
            "filter": "message",
            "string_splitter": {
                "source_fields": [
                    "message",
                ],
                "target_field": "message",
            },
        },
        event={
            "message": "this is the message",
        },
        expected={
            "message": "this is the message",
            "tags": [
                "_string_splitter_failure",
            ],
        },
        error_message=".*FieldExistsWarning.*",
    ),
]

parametrized_test_cases = [c.case_to_param() for c in test_cases]
parametrized_failure_test_cases = [c.case_to_param() for c in failure_test_cases]


class TestStringSplitter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "string_splitter",
        "rules": ["tests/testdata/unit/string_splitter/rules"],
    }

    @pytest.mark.parametrize("case", parametrized_test_cases)
    def test_testcases(self, case: ProcessorTestCase, provision_context_new):
        if case.context is not None:
            provision_context_new(case.context)
        self._load_rule(case.rule)
        assert isinstance(self.object, Processor)
        result = self.object.process(case.event)
        assert result.event is not None
        assert result.event["result"] == case.expected

    @pytest.mark.parametrize(["case"], parametrized_failure_test_cases)
    def test_testcases_failure_handling(
        self, case: ProcessorFailureTestCase, provision_context_new
    ):
        if case.context is not None:
            provision_context_new(case.context)
        self._load_rule(case.rule)
        assert isinstance(self.object, Processor)
        result = self.object.process(case.event)
        assert len(result.warnings) == 1
        assert re.match(case.error_message, str(result.warnings[0]))
        assert result.event == case.expected
