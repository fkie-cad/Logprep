# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
import re
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.sre_event import SreEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestPreDetector(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_pre_detector",
        "rules": ["tests/testdata/unit/pre_detector/rules"],
        "outputs": [{"kafka": "pre_detector_alerts"}],
        "alert_ip_list_path": "tests/testdata/unit/pre_detector/alert_ips.yml",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    uuid_pattern = re.compile(r"^[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}$")

    def test_perform_successful_pre_detection(self):
        document = {"winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}}}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_ONE_ID",
                    "title": "RULE_ONE",
                    "severity": "critical",
                    "mitre": ["attack.test1", "attack.test2"],
                    "case_condition": "directly",
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        assert event.extra_data
        assert len(event.extra_data) == 1, "one extra data item expected"
        assert isinstance(event.extra_data[0], SreEvent), "extra data should be SreEvent"
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_perform_pre_detection_that_fails_if_filter_children_were_slots(self):
        document = {"A": "foo X bar Y"}
        expected = deepcopy(document)
        event = LogEvent(document, original=b"")
        expected_detection_results = [
            (
                {
                    "case_condition": "directly",
                    "description": "Test rule four",
                    "id": "RULE_FOUR_ID",
                    "mitre": ["attack.test1", "attack.test2"],
                    "rule_filter": '(A:"*bar*" AND NOT ((A:"foo*" AND A:"*baz")))',
                    "severity": "critical",
                    "title": "RULE_FOUR",
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = self.object.process(event)
        _ = event.extra_data[0]
        self._assert_equality_of_results(event, expected, expected_detection_results)

        document = {"A": "foo X bar Y baz"}
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        assert event.extra_data == []

    def test_perform_successful_pre_detection_with_host_name(self):
        document = {
            "host": {"name": "Test hostname"},
            "winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}},
        }
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_ONE_ID",
                    "title": "RULE_ONE",
                    "severity": "critical",
                    "mitre": ["attack.test1", "attack.test2"],
                    "case_condition": "directly",
                    "host": {"name": "Test hostname"},
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_perform_successful_pre_detection_with_same_existing_pre_detection(self):
        document = {"winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}}}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_ONE_ID",
                    "title": "RULE_ONE",
                    "severity": "critical",
                    "mitre": ["attack.test1", "attack.test2"],
                    "case_condition": "directly",
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]

        document["pre_detection_id"] = "11fdfc1f-8e00-476e-b88f-753d92af989c"
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_perform_successful_pre_detection_with_pre_detector_complex_rule_suceeds_msg_t1(self):
        document = {"tags": "test", "process": {"program": "test"}, "message": "test1*xyz"}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_TWO_ID",
                    "title": "RULE_TWO",
                    "severity": "critical",
                    "mitre": [],
                    "case_condition": "directly",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND '
                    '(message:"test1*xyz" OR message:"test2*xyz"))',
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_perform_successful_pre_detection_with_pre_detector_complex_rule_succeeds_msg_t2(self):
        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2Xxyz"}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_THREE_ID",
                    "title": "RULE_THREE",
                    "severity": "critical",
                    "mitre": [],
                    "case_condition": "directly",
                    "description": "Test rule three",
                    "rule_filter": '(tags:"test2" AND process.program:"test" AND '
                    '(message:"test1*xyz" OR message:"test2?xyz"))',
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_perform_successful_pre_detection_with_two_rules(self):
        document = {"first_match": "something", "second_match": "something"}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "case_condition": "directly",
                    "id": "RULE_TWO_ID",
                    "mitre": ["attack.test2", "attack.test4"],
                    "description": "Test two rules two",
                    "rule_filter": '"second_match": *',
                    "severity": "suspicious",
                    "title": "RULE_TWO",
                },
                ({"kafka": "pre_detector_alerts"},),
            ),
            (
                {
                    "case_condition": "directly",
                    "id": "RULE_ONE_ID",
                    "mitre": ["attack.test1", "attack.test2"],
                    "description": "Test two rules one",
                    "rule_filter": '"first_match": *',
                    "severity": "critical",
                    "title": "RULE_ONE",
                },
                ({"kafka": "pre_detector_alerts"},),
            ),
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_correct_star_wildcard_behavior(self):
        document = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyzA"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyzA"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2*xyzA"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2*xyzA"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2xyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2xyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data != expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2Axyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2Axyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data != expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2AAxyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2AAxyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data != expected

    def test_correct_questionmark_wildcard_behavior(self):
        document = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyzA"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyzA"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2*xyzA"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2*xyzA"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2xyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2xyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data != expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2Axyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2Axyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data != expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2AAxyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2AAxyz"}
        event = LogEvent(document, original=b"")
        self.object.process(event)
        assert event.data == expected

    def test_ignores_case(self):
        document = {"tags": "test", "process": {"program": "test"}, "message": "TEST2*xyz"}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_TWO_ID",
                    "title": "RULE_TWO",
                    "severity": "critical",
                    "mitre": [],
                    "case_condition": "directly",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND (message:"test1*xyz" OR message:"test2*xyz"))',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def test_ignores_case_list(self):
        document = {"tags": "test", "process": {"program": "test"}, "message": ["TEST2*xyz"]}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "id": "RULE_TWO_ID",
                    "title": "RULE_TWO",
                    "severity": "critical",
                    "mitre": [],
                    "case_condition": "directly",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND (message:"test1*xyz" OR message:"test2*xyz"))',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        self._assert_equality_of_results(event, expected, expected_detection_results)

    def _assert_equality_of_results(
        self, event: LogEvent, expected: dict, expected_detection_results: list[dict]
    ) -> None:
        detection_results = [sre_event.data for sre_event in event.extra_data]
        for detection_result in detection_results:
            assert detection_result.pop("creation_timestamp")

        pre_detection_id = event.data.pop("pre_detection_id", None)

        assert pre_detection_id is not None
        assert self.uuid_pattern.search(pre_detection_id)
        assert event.data == expected

        for detection_result in detection_results:
            result_pre_detection_id = detection_result.pop("pre_detection_id", None)
            assert result_pre_detection_id is not None
            assert pre_detection_id == result_pre_detection_id

        sorted_detection_results = sorted(
            [(frozenset(sre_event.data), sre_event.outputs) for sre_event in event.extra_data]
        )
        sorted_expected_detection_results = sorted(
            [(frozenset(result[0]), result[1]) for result in expected_detection_results]
        )

        assert sorted_detection_results == sorted_expected_detection_results

    def test_adds_timestamp_to_extra_data_if_provided_by_event(self):
        rule = {
            "filter": 'winlog.event_id: 123 AND winlog.event_data.ServiceName: "VERY BAD"',
            "pre_detector": {
                "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                "title": "RULE_ONE",
                "severity": "critical",
                "mitre": ["attack.test1", "attack.test2"],
                "case_condition": "directly",
            },
            "description": "Test rule one",
        }
        document = {
            "@timestamp": "2024-08-12T12:13:04+00:00",
            "winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}},
        }
        self._load_rule(rule)
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        sre_event = event.extra_data[0]
        assert sre_event.data.get("@timestamp") == "2024-08-12T12:13:04Z"

    @pytest.mark.parametrize(
        "testcase, rule, timestamp, expected",
        [
            (
                "UNIX timestamp",
                {
                    "filter": "*",
                    "pre_detector": {
                        "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                        "title": "RULE_ONE",
                        "severity": "critical",
                        "mitre": ["attack.test1", "attack.test2"],
                        "case_condition": "directly",
                        "source_format": "UNIX",
                    },
                    "description": "Test rule one",
                },
                "1723464784",
                "2024-08-12T12:13:04Z",
            ),
            (
                "format from given source_formats list in configuration",
                {
                    "filter": "*",
                    "pre_detector": {
                        "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                        "title": "RULE_ONE",
                        "severity": "critical",
                        "mitre": ["attack.test1", "attack.test2"],
                        "case_condition": "directly",
                        "source_format": "%Y%m%d%H%M%S",
                    },
                    "description": "Test rule one",
                },
                "20000117113704",
                "2000-01-17T11:37:04Z",
            ),
            (
                "already normalized timestamp",
                {
                    "filter": "*",
                    "pre_detector": {
                        "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                        "title": "RULE_ONE",
                        "severity": "critical",
                        "mitre": ["attack.test1", "attack.test2"],
                        "case_condition": "directly",
                    },
                    "description": "Test rule one",
                },
                "2024-11-11T11:11:11+00:00",
                "2024-11-11T11:11:11Z",
            ),
        ],
    )
    def test_timestamp_is_normalized(self, testcase, rule, timestamp, expected):
        self._load_rule(rule)
        document = {
            "@timestamp": timestamp,
            "winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}},
        }
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        sre_event = event.extra_data[0]
        assert sre_event.data.get("@timestamp") == expected, testcase

    def test_custom_timestamp_field_can_be_used(self):
        rule = {
            "filter": "*",
            "pre_detector": {
                "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                "title": "RULE_ONE",
                "severity": "critical",
                "mitre": ["attack.test1", "attack.test2"],
                "case_condition": "directly",
                "timestamp_field": "custom_timestamp",
                "source_format": "%Y%m%d%H%M%S",
            },
            "description": "Test rule one",
        }
        document = {
            "first_match": "something",
            "custom_timestamp": "20240811021145",
            "second_match": "something",
            "@timestamp": "19960531153655",
        }
        self._load_rule(rule)
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        sre_event = event.extra_data[0]
        assert sre_event.data.get("custom_timestamp") == "2024-08-11T02:11:45Z"
        assert sre_event.data.get("@timestamp") is None, "should not be in detection data"

    def test_appends_processing_warning_if_timestamp_could_not_be_parsed(self):
        rule = {
            "filter": "*",
            "pre_detector": {
                "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                "title": "RULE_ONE",
                "severity": "critical",
                "mitre": ["attack.test1", "attack.test2"],
                "case_condition": "directly",
            },
            "description": "Test rule one",
        }
        document = {
            "@timestamp": "this is not a timestamp",
        }
        self._load_rule(rule)
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        assert event.warnings
        assert len(event.warnings) == 1
        assert "Could not parse timestamp" in str(event.warnings[0])
        assert document, "should not be cleared"
        assert document.get("@timestamp") == "this is not a timestamp", "should not be modified"
        assert "tags" in document
        assert "_pre_detector_failure" in document["tags"]
        assert "_pre_detector_timeparsing_failure" in document["tags"]

    def test_generate_detection_result_does_not_modify_rule_data(self):
        rule = {
            "filter": "*",
            "pre_detector": {
                "id": "ac1f47e4-9f6f-4cd4-8738-795df8bd5d4f",
                "title": "RULE_ONE",
                "severity": "critical",
                "mitre": ["attack.test1", "attack.test2"],
                "case_condition": "directly",
            },
            "description": "Test rule one",
        }
        self._load_rule(rule)
        document = {"winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}}}
        event = LogEvent(document, original=b"")
        event = self.object.process(event)
        assert (
            "rule_filter" not in self.object.rules[0].detection_data
        ), "rule_filter should not be in detection data"
