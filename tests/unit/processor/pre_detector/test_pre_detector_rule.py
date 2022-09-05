from logprep.filter.lucene_filter import LuceneFilter

import pytest

pytest.importorskip("logprep.processor.pre_detector")

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


class TestNormalizerRule:
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
        rule1 = PreDetectorRule(
            LuceneFilter.create(specific_rule_definition["filter"]),
            specific_rule_definition["pre_detector"],
            specific_rule_definition.get("ip_fields"),
        )
        rule2 = PreDetectorRule(
            LuceneFilter.create(other_rule_definition["filter"]),
            other_rule_definition["pre_detector"],
            other_rule_definition.get("ip_fields"),
        )
        assert (rule1 == rule2) == is_equal, testcase
