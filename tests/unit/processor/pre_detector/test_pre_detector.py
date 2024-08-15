# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
import re
from copy import deepcopy

import pytest

from tests.unit.processor.base import BaseProcessorTestCase


class TestPreDetector(BaseProcessorTestCase):
    CONFIG = {
        "type": "pre_detector",
        "generic_rules": ["tests/testdata/unit/pre_detector/rules/generic"],
        "specific_rules": ["tests/testdata/unit/pre_detector/rules/specific"],
        "outputs": [{"kafka": "pre_detector_alerts"}],
        "alert_ip_list_path": "tests/testdata/unit/pre_detector/alert_ips.yml",
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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

    def test_perform_pre_detection_that_fails_if_filter_children_were_slots(self):
        document = {"A": "foo X bar Y"}
        expected = deepcopy(document)
        expected_detection_results = [
            (
                {
                    "case_condition": "directly",
                    "description": "Test rule four",
                    "id": "RULE_FOUR_ID",
                    "mitre": ["attack.test1", "attack.test2"],
                    "rule_filter": '(A:"*bar*" AND NOT ((A:"foo*" AND A:"*baz")))',
                    "severity": "critical",
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "title": "RULE_FOUR",
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

        document = {"A": "foo X bar Y baz"}
        detection_results = self.object.process(document)
        assert detection_results.data == []

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule one",
                    "rule_filter": '(winlog.event_id:"123" AND winlog.event_data.ServiceName:"VERY BAD")',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]

        document["pre_detection_id"] = "11fdfc1f-8e00-476e-b88f-753d92af989c"
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND '
                    '(message:"test1*xyz" OR message:"test2*xyz"))',
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule three",
                    "rule_filter": '(tags:"test2" AND process.program:"test" AND '
                    '(message:"test1*xyz" OR message:"test2?xyz"))',
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "title": "RULE_ONE",
                },
                ({"kafka": "pre_detector_alerts"},),
            ),
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

    def test_correct_star_wildcard_behavior(self):
        document = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyz"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyzA"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test3*xyzA"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2*xyzA"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2*xyzA"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2xyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2xyz"}
        self.object.process(document)
        assert document != expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2Axyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2Axyz"}
        self.object.process(document)
        assert document != expected

        document = {"tags": "test", "process": {"program": "test"}, "message": "test2AAxyz"}
        expected = {"tags": "test", "process": {"program": "test"}, "message": "test2AAxyz"}
        self.object.process(document)
        assert document != expected

    def test_correct_questionmark_wildcard_behavior(self):
        document = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyz"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyzA"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test3*xyzA"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2*xyzA"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2*xyzA"}
        self.object.process(document)
        assert document == expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2xyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2xyz"}
        self.object.process(document)
        assert document != expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2Axyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2Axyz"}
        self.object.process(document)
        assert document != expected

        document = {"tags": "test2", "process": {"program": "test"}, "message": "test2AAxyz"}
        expected = {"tags": "test2", "process": {"program": "test"}, "message": "test2AAxyz"}
        self.object.process(document)
        assert document == expected

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND (message:"test1*xyz" OR message:"test2*xyz"))',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

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
                    "target_timezone": "UTC",
                    "source_timezone": "UTC",
                    "source_formats": "ISO8601",
                    "timestamp_field": "@timestamp",
                    "description": "Test rule two",
                    "rule_filter": '(tags:"test" AND process.program:"test" AND (message:"test1*xyz" OR message:"test2*xyz"))',  # pylint: disable=line-too-long
                },
                ({"kafka": "pre_detector_alerts"},),
            )
        ]
        detection_results = self.object.process(document)
        self._assert_equality_of_results(
            document, expected, detection_results.data, expected_detection_results
        )

    def _assert_equality_of_results(
        self, document, expected, detection_results, expected_detection_results
    ):
        for detection_result, _ in detection_results:
            assert detection_result.pop("creation_timestamp")

        pre_detection_id = document.pop("pre_detection_id", None)

        assert pre_detection_id is not None
        assert self.uuid_pattern.search(pre_detection_id)
        assert document == expected

        for detection_result, _ in detection_results:
            result_pre_detection_id = detection_result.pop("pre_detection_id", None)
            assert result_pre_detection_id is not None
            assert pre_detection_id == result_pre_detection_id

        sorted_detection_results = sorted(
            [(frozenset(result[0]), result[1]) for result in detection_results]
        )
        sorted_expected_detection_results = sorted(
            [(frozenset(result[0]), result[1]) for result in expected_detection_results]
        )

        assert sorted_detection_results == sorted_expected_detection_results

    def test_adds_timestamp_to_extra_data_if_provided_by_event(self):
        document = {
            "@timestamp": "2024-08-12T12:13:04+00:00",
            "winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}},
        }
        detection_results = self.object.process(document)
        assert detection_results.data[0][0].get("@timestamp") == "2024-08-12T12:13:04Z"

    @pytest.mark.parametrize(
        "testcase, timestamp, expected",
        [
            ("UNIX timestamp", "1723464784", "2024-08-12T12:13:04Z"),
            (
                "format from given source_formats list in configuration",
                "20000117113704",
                "2000-01-17T11:37:04Z",
            ),
            ("already normalized timestamp", "2024-11-11T11:11:11+00:00", "2024-11-11T11:11:11Z"),
        ],
    )
    def test_timestamp_is_normalized(self, testcase, timestamp, expected):
        document = {
            "@timestamp": timestamp,
            "winlog": {"event_id": 123, "event_data": {"ServiceName": "VERY BAD"}},
        }
        detection_results = self.object.process(document)
        assert detection_results.data[0][0].get("@timestamp") == expected, testcase

    def test_custom_timestamp_field_can_be_used(self):
        document = {
            "first_match": "something",
            "custom_timestamp": "20240811021145",
            "second_match": "something",
            "@timestamp": "19960531153655",
        }
        detection_results = self.object.process(document)
        assert detection_results.data[0][0].get("custom_timestamp") == "2024-08-11T02:11:45Z"
        assert detection_results.data[0][0].get("@timestamp") == "1996-05-31T15:36:55Z"
