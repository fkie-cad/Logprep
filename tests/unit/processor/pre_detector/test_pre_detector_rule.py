# pylint: disable=missing-docstring
# pylint: disable=protected-access

import pytest

from logprep.processor.pre_detector.rule import PreDetectorRule


@pytest.fixture()
def specific_rule_definition():
    return {
        "filter": "message",
        "pre_detector": {
            "id": "RULE_ONE_ID",
            "title": "Rule one",
            "severity": "critical",
            "mitre": ["some_tag"],
            "case_condition": "directly",
        },
        "description": "Some malicous event.",
        "ip_fields": ["some_ip_field"],
    }


class TestPreDetectorRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "description": "Some malicous event.",
                    "ip_fields": ["some_ip_field"],
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause no ip_fields",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                },
                False,
            ),
            (
                "Should be not equal cause other ip_fields",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_other_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause other id",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "OTHER_RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause other title",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Other rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause other severity",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "low",
                        "mitre": ["some_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause other mitre",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_other_tag"],
                        "case_condition": "directly",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
            (
                "Should be not equal cause other case_condition",
                {
                    "filter": "message",
                    "pre_detector": {
                        "id": "RULE_ONE_ID",
                        "title": "Rule one",
                        "severity": "critical",
                        "mitre": ["some_tag"],
                        "case_condition": "other",
                    },
                    "ip_fields": ["some_ip_field"],
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = PreDetectorRule._create_from_dict(specific_rule_definition)
        rule2 = PreDetectorRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
