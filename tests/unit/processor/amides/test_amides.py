# pylint: disable=missing-docstring
# pylint: disable=protected-access
import hashlib
import logging
import re
from copy import deepcopy
from multiprocessing import current_process
from pathlib import Path

import pytest
import responses

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
        self.object.setup()
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

        result = document.get("amides")
        assert result
        assert result["confidence"] >= self.CONFIG.get("decision_threshold") and result.get(
            "attributions"
        )
        assert len(result["attributions"]) == 10
        assert self.object.metrics.total_cmdlines == 1
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2
        assert self.object.metrics.mean_misuse_detection_time != 0.0
        assert self.object.metrics.mean_rule_attribution_time != 0.0

    def test_process_event_benign_process_command_line(self):
        self.object.setup()
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
        result = document.get("amides")
        assert result
        assert result["confidence"] < self.CONFIG.get("decision_threshold") and not result.get(
            "attributions"
        )
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
        self.object.setup()
        assert self.object.metrics.number_of_processed_events == 0

        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1
        assert not document.get("amides")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0
        assert self.object.metrics.mean_misuse_detection_time == 0.0
        assert self.object.metrics.mean_rule_attribution_time == 0.0

    def test_process_event_without_command_line_field(self):
        self.object.setup()
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"event_id": 1, "provider_name": "Microsoft-Windows-Sysmon"},
            "some": {"random": "data"},
        }

        self.object.process(document)
        assert self.object.metrics.number_of_processed_events == 1
        assert not document.get("amides")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0
        assert self.object.metrics.mean_misuse_detection_time == 0.0
        assert self.object.metrics.mean_rule_attribution_time == 0.0

    def test_classification_results_from_cache(self):
        self.object.setup()
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

        assert other_document.get("amides") == document.get("amides")
        assert self.object.metrics.total_cmdlines == 2
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2
        assert self.object.metrics.mean_misuse_detection_time != 0.0
        assert self.object.metrics.mean_rule_attribution_time != 0.0

    def test_process_event_raise_duplication_error(self, caplog):
        self.object.setup()
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            }
        }
        self.object.process(document)
        assert document.get("amides")
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*", caplog.text)

    def test_setup_get_model_via_file_getter(self, tmp_path, monkeypatch):
        model_uri = "file://tests/testdata/unit/amides/model.zip"
        model_original = Path(self.CONFIG["models_path"])
        expected_checksum = hashlib.md5(model_original.read_bytes()).hexdigest()  # nosemgrep

        (tmp_path / model_original.parent).mkdir(parents=True)
        model_test_copy = tmp_path / model_original
        model_test_copy.touch()
        model_test_copy.write_bytes(model_original.read_bytes())

        self.object._config.models_path = model_uri

        with monkeypatch.context() as monkey_context:
            monkey_context.chdir(tmp_path)
            self.object.setup()
            cached_file = Path(f"{current_process().name}-{self.object.name}.zip")
            assert cached_file.exists()
            cached_checksum = hashlib.md5(cached_file.read_bytes()).hexdigest()  # nosemgrep
            assert expected_checksum == cached_checksum

    @responses.activate
    def test_setup_get_model_via_http_getter(self, tmp_path, monkeypatch):
        model_uri = "http://model-path-target/model.zip"
        model_original = Path(self.CONFIG["models_path"])
        model_original_content = model_original.read_bytes()
        expected_checksum = hashlib.md5(model_original_content).hexdigest()  # nosemgrep
        responses.add(responses.GET, model_uri, model_original_content)

        self.object._config.models_path = model_uri

        with monkeypatch.context() as monkey_context:
            monkey_context.chdir(tmp_path)
            self.object.setup()
            loaded_file = Path(f"{current_process().name}-{self.object.name}.zip")
            assert loaded_file.exists()
            loaded_checksum = hashlib.md5(loaded_file.read_bytes()).hexdigest()  # nosemgrep
            assert expected_checksum == loaded_checksum
