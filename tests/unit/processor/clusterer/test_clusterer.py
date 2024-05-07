# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
from copy import deepcopy
from unittest import mock

from logprep.factory import Factory
from logprep.processor.clusterer.rule import ClustererRule
from tests.unit.processor.base import BaseProcessorTestCase


class TestClusterer(BaseProcessorTestCase):
    CONFIG = {
        "type": "clusterer",
        "output_field_name": "cluster_signature",
        "generic_rules": ["tests/testdata/unit/clusterer/rules/generic"],
        "specific_rules": ["tests/testdata/unit/clusterer/rules/specific"],
    }

    def test_has_tag_clusterable(self):
        # Sample without PRI, since PRI makes a log clusterable irrespective of the tag
        sample_syslog_without_pri = {
            "severity_label": "Informational",
            "pid": "1339",
            "host": "172.16.0.2",
            "timestamp": "2019-02-04T14:06:00.010548+01:00",
            "logsource": "internalserver",
            "priority": 30,
            "@timestamp": "2019-02-04T13:06:00.010Z",
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
            "program": "ntpd",
            "syslog": {
                "facility_label": "system",
                "priority": 30,
                "severity_label": "Informational",
            },
            "@version": "1",
            "tags": ["clusterable"],
            "timestamp8601": "2019-02-04T14:06:00.010548+01:00",
        }
        sample_winevtlog = {
            "type": "wineventlog",
            "winlog": {
                "event_data": {
                    "param1": "Windows Defender",
                    "param2": "running",
                    "Binary": "570069006E0044006500660065006E0064002F0034000000",
                }
            },
            "process_id": 440,
            "provider_guid": "{555908d1-a6d7-4695-8e1e-26931d2012f4}",
            "beat": {"name": "CLIENT1", "version": "6.3.1", "hostname": "CLIENT1"},
            "record_number": "11234",
            "host": {"name": "CLIENT1"},
            "tags": ["beats_input_codec_plain_applied"],
            "keywords": ["Classic"],
            "level": "Information",
            "thread_id": 560,
            "log_name": "System",
            "@timestamp": "2019-02-04T13:09:56.036Z",
            "computer_name": "CLIENT1.breach.local",
            "message": "The Windows Defender service entered the running state.",
            "source_name": "Service Control Manager",
            "@version": "1",
            "event_id": 7036,
        }
        invalid_syslog_with_missing_tag = {"message": "Listen normally on 5 lo ::1 UDP 123\n"}
        invalid_syslog_with_none_message = {"message": None, "tags": ["clusterable"]}

        assert self.object._is_clusterable(sample_syslog_without_pri, "message")
        assert not self.object._is_clusterable(sample_winevtlog, "message")
        assert not self.object._is_clusterable(invalid_syslog_with_missing_tag, "message")
        assert not self.object._is_clusterable(invalid_syslog_with_none_message, "message")

    @mock.patch("logprep.processor.clusterer.processor.Clusterer._is_clusterable")
    @mock.patch("logprep.processor.clusterer.processor.Clusterer._cluster")
    def test_only_clusterable_logs_are_clustered(self, mock_cluster, mock_is_clusterable):
        mock_is_clusterable.return_value = False
        self.object.process({"message": "test_message"})
        mock_is_clusterable.assert_called()
        mock_cluster.assert_not_called()

        mock_is_clusterable.return_value = True
        self.object.process({"message": "test_message"})
        mock_is_clusterable.assert_called()
        assert mock_cluster.call_count == 2

    def test_syslog_has_severity_and_facility(self):
        valid_syslog_with_facility_and_severity = {
            "syslog": {"facility": 3},
            "event": {"severity": 6},
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
        }
        invalid_syslog_with_missing_severity_and_facility = {
            "message": "Listen normally on 5 lo ::1 UDP 123\n"
        }

        assert self.object._syslog_has_pri(valid_syslog_with_facility_and_severity)
        assert not self.object._syslog_has_pri(invalid_syslog_with_missing_severity_and_facility)

    def test_clusterable_field_determines_if_clusterable(self):
        """Check if clusterable has precedence over the existence of facility and severity"""
        log_with_clusterable_field_equals_true = {
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
            "clusterable": True,
        }
        log_with_clusterable_field_equals_false = {
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
            "clusterable": False,
        }
        valid_syslog_with_clusterable_field_equals_true = {
            "syslog": {"facility": 3},
            "event": {"severity": 6},
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
            "clusterable": True,
        }
        syslog_with_clusterable_field_equals_false = {
            "syslog": {"facility": 3},
            "event": {"severity": "6"},
            "message": "Listen normally on 5 lo ::1 UDP 123\n",
            "clusterable": False,
        }

        assert self.object._is_clusterable(log_with_clusterable_field_equals_true, "message")
        assert self.object._is_clusterable(
            valid_syslog_with_clusterable_field_equals_true, "message"
        )
        assert not self.object._is_clusterable(log_with_clusterable_field_equals_false, "message")
        assert not self.object._is_clusterable(
            syslog_with_clusterable_field_equals_false, "message"
        )

    def test_rule_tests(self):
        rule_definition = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"test (signature) test",
                "repl": r"<+>\1</+>",
            },
            "description": "insert a description text",
            "tests": {"raw": "test signature test", "result": "<+>signature</+>"},
        }

        rule = ClustererRule._create_from_dict(rule_definition)
        self.object.rules.append(rule)

        results = self.object.test_rules()
        for rule_results in results.values():
            for result, expected in rule_results:
                assert result == expected

    def test_cluster(self):
        rule_definition = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"test (signature) test",
                "repl": r"<+>\1</+>",
            },
            "description": "insert a description text",
            "tests": {"raw": "test signature test", "result": "<+>signature</+>"},
        }

        expected = {
            "cluster_signature": "signature",
            "message": "test signature test",
        }

        document = {"message": "test signature test"}
        rule = ClustererRule._create_from_dict(rule_definition)
        self.object._generic_tree.add_rule(rule, None)
        self.object._cluster(document, rule)

        assert document == expected

    def test_rule_dependency(self, tmp_path):
        config = deepcopy(self.CONFIG)
        empty_rules_path = tmp_path / "empty"
        empty_rules_path.mkdir()
        config.update({"generic_rules": [empty_rules_path.as_posix()]})
        config.update({"specific_rules": [empty_rules_path.as_posix()]})
        clusterer = Factory.create({"test instance": config}, self.logger)

        rule_0 = {
            "filter": "no_match",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"sig(\w*)",
                "repl": r"<+>sig\1</+>",
            },
            "description": "",
        }

        rule_1 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"sig(\w*)",
                "repl": r"<+>sig\1</+>",
            },
            "description": "",
        }
        rule_2 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": "foo",
                "repl": "bar",
            },
            "description": "",
        }
        rule_3 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": "bar",
                "repl": "baz",
            },
            "description": "",
        }
        rule_4 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"(baz)",
                "repl": r"<+>\1</+>",
            },
            "description": "",
        }
        rules = [rule_0, rule_1, rule_2, rule_3, rule_4]
        specific_rules = []
        for idx, rule in enumerate(rules):
            new_rule = ClustererRule._create_from_dict(rule)
            new_rule.file_name = str(idx)
            specific_rules.append(new_rule)
            clusterer._specific_tree.add_rule(new_rule, None)
        rule_5 = {
            "filter": "no_match",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"signature",
                "repl": r"SIGN",
            },
            "description": "",
        }
        rule_6 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"signature",
                "repl": r"SIGN",
            },
            "description": "",
        }
        rule_7 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"(SIGN)",
                "repl": r"<+>\1</+>",
            },
            "description": "",
        }
        rule_8 = {
            "filter": "message",
            "clusterer": {
                "source_fields": ["message"],
                "pattern": r"(test)",
                "repl": r"<+>\1</+>",
            },
            "description": "",
        }
        rules = [rule_5, rule_6, rule_7, rule_8]
        generic_rules = []

        for idx, rule in enumerate(rules):
            new_rule = ClustererRule._create_from_dict(rule)
            new_rule.file_name = str(idx)
            generic_rules.append(new_rule)
            clusterer._generic_tree.add_rule(new_rule, None)

        expected = {
            "message": "test some signature xyz-foo",
            "cluster_signature": "signature baz",
        }

        document = {"message": "test some signature xyz-foo"}
        for rule in specific_rules:
            clusterer._cluster(document, rule)
        assert document == expected

        document = {"message": "test some signature xyz-foo"}
        for rule in specific_rules:
            clusterer._cluster(document, rule)
        assert document == expected

        document = {"message": "test some signature xyz-foo"}
        for rule in specific_rules[1:]:
            clusterer._cluster(document, rule)
        assert document == expected

        expected = {
            "message": "test some signature xyz-foo",
            "cluster_signature": "test SIGN",
        }
        document = {"message": "test some signature xyz-foo"}
        for rule in specific_rules + generic_rules:
            clusterer._cluster(document, rule)
        assert document == expected
