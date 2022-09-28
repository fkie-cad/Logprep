# pylint: disable=missing-docstring
import pytest
from tests.unit.processor.base import BaseProcessorTestCase
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.util.json_handling import parse_json

test_cases = parse_json("tests/unit/processor/dissecter/testcases.json")

failure_test_cases = [  # testcase, rule, event, expected
    (
        "Tags failure if convert is not possible",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I cant't be converted into int"},
        {
            "message": "I cant't be converted into int",
            "tags": ["_dissectfailure"],
        },
    ),
    (
        "Tags failure if convert is not possible and extends tags list",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
            },
        },
        {"message": "I cant't be converted into int", "tags": ["preexisting"]},
        {
            "message": "I cant't be converted into int",
            "tags": ["preexisting", "_dissectfailure"],
        },
    ),
    (
        "Tags custom failure if convert is not possible",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag2"],
            },
        },
        {"message": "I cant't be converted into int"},
        {
            "message": "I cant't be converted into int",
            "tags": ["custom_tag_1", "custom_tag2"],
        },
    ),
    (
        "Tags custom failure if convert is not possible and extends tag list",
        {
            "filter": "message",
            "dissecter": {
                "convert_datatype": {
                    "message": "int",
                },
                "tag_on_failure": ["custom_tag_1", "custom_tag2"],
            },
        },
        {"message": "I cant't be converted into int", "tags": ["preexisting1", "preexisting2"]},
        {
            "message": "I cant't be converted into int",
            "tags": ["preexisting1", "preexisting2", "custom_tag_1", "custom_tag2"],
        },
    ),
    (
        "Tags  failure if mapping field does not exist",
        {"filter": "message", "dissecter": {"mapping": {"doesnotexist": "%{} %{}"}}},
        {"message": "This is the message which does not matter"},
        {"message": "This is the message which does not matter", "tags": ["_dissectfailure"]},
    ),
]


class TestDissecter(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "dissecter",
        "generic_rules": ["tests/testdata/unit/dissecter"],
        "specific_rules": ["tests/testdata/unit/dissecter"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected
