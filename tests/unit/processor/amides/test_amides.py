# pylint: disable=missing-docstring
# pylint: disable=protected-access
from copy import deepcopy
import pytest

from logprep.processor.amides.processor import AmidesError
from tests.unit.processor.base import BaseProcessorTestCase


class TestAmides(BaseProcessorTestCase):
    CONFIG = {
        "type": "amides",
        "generic_rules": ["tests/testdata/unit/amides/rules/generic"],
        "specific_rules": ["tests/testdata/unit/amides/rules/specific"],
        "models_path": "tests/testdata/unit/amides/model.zip",
        "max_cache_entries": 5,
        "decision_threshold": 0.32,
        "num_rule_attributions": 10,
    }

    def test_process_event_malicious_process_command_line(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            },
        }

        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1

        rule_attributions = document.get("rule_attributions", None)
        assert rule_attributions
        assert len(rule_attributions) == 10
        assert self.object.metrics.total_cmdlines == 1
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2
        assert self.object.metrics.mean_misuse_detection_time != 0.0
        assert self.object.metrics.mean_rule_attribution_time != 0.0

    def test_process_event_benign_process_command_line(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "C:\\Windows\\system32\\svchost.exe -k DcomLaunch"},
            },
        }
        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1
        assert not document.get("rule_attributions")
        assert self.object.metrics.total_cmdlines == 1
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2
        assert self.object.metrics.mean_misuse_detection_time != 0.0
        assert self.object.metrics.mean_rule_attribution_time == 0.0

    no_pc_events = [
        {"winlog": {"event_id": 6005, "provider_name": "Microsoft-Windows-Sysmon"}},
        {"winlog": {"event_id": 1, "provider_name": "Microsoft-Windows-Kernel-General"}},
        {"winlog": {"event_id": 1}},
        {"winlog": {"provider_name": "Microsoft-Windows-Sysmon"}},
    ]

    @pytest.mark.parametrize("document", no_pc_events)
    def test_process_event_no_process_creation_events(self, document):
        assert self.object.metrics.number_of_processed_events == 0

        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1
        assert not document.get("rule_attributions")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0
        assert self.object.metrics.mean_misuse_detection_time == 0.0
        assert self.object.metrics.mean_rule_attribution_time == 0.0

    def test_process_event_without_command_line_field(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"event_id": 1, "provider_name": "Microsoft-Windows-Sysmon"},
            "some": {"random": "data"},
        }

        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1
        assert not document.get("rule_attributions")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0
        assert self.object.metrics.mean_misuse_detection_time == 0.0
        assert self.object.metrics.mean_rule_attribution_time == 0.0

    def test_classification_results_from_cache(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            }
        }
        other_document = deepcopy(document)

        self.object.process(document)
        self.object.process(other_document)
        assert self.object.metrics.number_of_processed_events == 2

        assert other_document.get("rule_attributions") == document.get("rule_attributions")
        assert self.object.metrics.total_cmdlines == 2
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2
        assert self.object.metrics.mean_misuse_detection_time != 0.0
        assert self.object.metrics.mean_rule_attribution_time != 0.0

    def test_process_event_with_confidence_values(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            }
        }
        self.object.process(document)
        assert document.get("rule_attributions")

        with pytest.raises(AmidesError):
            self.object.process(document)
