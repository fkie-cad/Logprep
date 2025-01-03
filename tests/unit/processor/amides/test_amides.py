# pylint: disable=missing-docstring
# pylint: disable=protected-access
import hashlib
import re
from copy import deepcopy
from multiprocessing import current_process
from pathlib import Path

import pytest
import responses

from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase


@pytest.mark.filterwarnings("ignore:Trying to unpickle.*")
class TestAmides(BaseProcessorTestCase):
    CONFIG = {
        "type": "amides",
        "rules": ["tests/testdata/unit/amides/rules"],
        "models_path": "tests/testdata/unit/amides/model.zip",
        "max_cache_entries": 5,
        "decision_threshold": 0.32,
        "num_rule_attributions": 10,
    }

    expected_metrics = [
        "logprep_amides_total_cmdlines",
        "logprep_amides_new_results",
        "logprep_amides_cached_results",
        "logprep_amides_num_cache_entries",
        "logprep_amides_cache_load",
        "logprep_amides_mean_misuse_detection_time",
        "logprep_amides_mean_rule_attribution_time",
    ]

    def test_process_event_malicious_process_command_line(self):
        self.object.metrics.total_cmdlines = 0
        self.object.metrics.new_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.metrics.cache_load = 0.0
        self.object.setup()
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            },
        }

        self.object.process(document)

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

    def test_process_event_benign_process_command_line(self):
        self.object.metrics.total_cmdlines = 0
        self.object.metrics.new_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.metrics.cache_load = 0.0
        self.object.setup()
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "C:\\Windows\\system32\\svchost.exe -k DcomLaunch"},
            },
        }
        self.object.process(document)
        result = document.get("amides")
        assert result
        assert result["confidence"] < self.CONFIG.get("decision_threshold") and not result.get(
            "attributions"
        )
        assert self.object.metrics.total_cmdlines == 1
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.num_cache_entries == 1
        assert self.object.metrics.cache_load == 0.2

    no_pc_events = [
        {"winlog": {"event_id": 6005, "provider_name": "Microsoft-Windows-Sysmon"}},
        {"winlog": {"event_id": 1, "provider_name": "Microsoft-Windows-Kernel-General"}},
        {"winlog": {"event_id": 1}},
        {"winlog": {"provider_name": "Microsoft-Windows-Sysmon"}},
    ]

    @pytest.mark.parametrize("document", no_pc_events)
    def test_process_event_no_process_creation_events(self, document):
        self.object.metrics.total_cmdlines = 0
        self.object.metrics.new_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.metrics.cache_load = 0.0
        self.object.setup()

        self.object.process(document)
        assert not document.get("amides")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0

    def test_process_event_without_command_line_field(self):
        self.object.metrics.total_cmdlines = 0
        self.object.metrics.new_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.metrics.cache_load = 0.0
        self.object.setup()
        document = {
            "winlog": {"event_id": 1, "provider_name": "Microsoft-Windows-Sysmon"},
            "some": {"random": "data"},
        }

        self.object.process(document)
        assert not document.get("amides")
        assert self.object.metrics.total_cmdlines == 0
        assert self.object.metrics.new_results == 0
        assert self.object.metrics.num_cache_entries == 0
        assert self.object.metrics.cache_load == 0.0

    def test_classification_results_from_cache(self):
        self.object.metrics.total_cmdlines = 0
        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.metrics.cache_load = 0.0
        self.object.setup()
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

        assert other_document.get("amides") == document.get("amides")
        assert self.object.metrics.total_cmdlines == 2
        # we mock the metrics with integer operations, so the assertions
        # are a little bit weird:
        # we assert for 2 because we add two times the same cache result
        # the underlying metric implementation sets the values instead of adding
        # them
        assert self.object.metrics.new_results == 2
        assert self.object.metrics.num_cache_entries == 2
        assert self.object.metrics.cache_load == 0.4
        # end strange mock
        assert self.object.metrics.cached_results == 1

    def test_process_event_raise_duplication_error(self):
        self.object.setup()
        document = {
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"CommandLine": "cmd.exe /c taskkill.exe /im cmd.exe"},
            }
        }
        self.object.process(document)
        assert document.get("amides")
        result = self.object.process(document)
        assert len(result.warnings) > 0
        assert re.match(
            r".*missing source_fields: \['process.command_line'].*", str(result.warnings)
        )
        assert re.match(".*FieldExistsWarning.*", str(result.warnings))

    def test_setup_get_model_via_file_getter(self, tmp_path, monkeypatch):
        model_uri = "file://tests/testdata/unit/amides/model.zip"
        model_original = Path(self.CONFIG["models_path"])
        expected_checksum = hashlib.md5(model_original.read_bytes()).hexdigest()  # nosemgrep

        (tmp_path / model_original.parent).mkdir(parents=True)
        model_test_copy = tmp_path / model_original
        model_test_copy.touch()
        model_test_copy.write_bytes(model_original.read_bytes())

        config = deepcopy(self.CONFIG)
        config["models_path"] = model_uri
        self.object = Factory.create({"amides": config})

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

        config = deepcopy(self.CONFIG)
        config["models_path"] = model_uri
        self.object = Factory.create({"amides": config})

        with monkeypatch.context() as monkey_context:
            monkey_context.chdir(tmp_path)
            self.object.setup()
            loaded_file = Path(f"{current_process().name}-{self.object.name}.zip")
            assert loaded_file.exists()
            loaded_checksum = hashlib.md5(loaded_file.read_bytes()).hexdigest()  # nosemgrep
            assert expected_checksum == loaded_checksum
