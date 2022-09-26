# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=attribute-defined-outside-init
import json
import logging
import os
import re
import tempfile
from unittest import mock

from logprep.util.rule_dry_runner import DryRunner


class TestRunLogprep:
    def setup_method(self):
        config = """
        process_count: 1
        timeout: 0.1

        pipeline:
          - normalizer:
              type: normalizer
              specific_rules:
                - tests/testdata/unit/normalizer/rules/specific/
              generic_rules:
                - tests/testdata/unit/normalizer/rules/generic/
              regex_mapping: tests/testdata/unit/normalizer/regex_mapping.yml
          - labelername:
              type: labeler
              schema: tests/testdata/unit/labeler/schemas/schema3.json
              include_parent_labels: true
              specific_rules:
                - tests/testdata/unit/labeler/rules/specific/
              generic_rules:
                - tests/testdata/unit/labeler/rules/generic/
          - pseudonymizer:
              type: pseudonymizer
              pubkey_analyst: tests/testdata/unit/pseudonymizer/example_analyst_pub.pem
              pubkey_depseudo: tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem
              regex_mapping: tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml
              hash_salt: a_secret_tasty_ingredient
              pseudonyms_topic: pseudonyms
              specific_rules:
                - tests/testdata/unit/pseudonymizer/rules/specific/
              generic_rules:
                - tests/testdata/unit/pseudonymizer/rules/generic/
              max_cached_pseudonyms: 1000000
              max_caching_days: 1
          - predetectorname:
              type: pre_detector
              specific_rules:
                - tests/testdata/unit/pre_detector/rules/specific/
              generic_rules:
                - tests/testdata/unit/pre_detector/rules/generic/
              pre_detector_topic: sre_topic
        """
        self.config_path = os.path.join(tempfile.gettempdir(), "dry-run-config.yml")
        with open(self.config_path, "w", encoding="utf8") as config_file:
            config_file.write(config)

    def teardown_method(self):
        os.remove(self.config_path)

    def test_dry_run_accepts_json_as_input(self, tmp_path, capsys):
        test_json = {"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=self.config_path,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_json_in_list_as_input(self, tmp_path, capsys):
        test_json = [{"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}]
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=self.config_path,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_jsonl_as_input(self, tmp_path, capsys):
        test_jsonl = [
            '{"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}\n',
            '{"winlog": {"event_id": 1111, "event_data": {"test2": "more fancy data"}}}',
        ]
        input_jsonl_file = os.path.join(tmp_path, "test_input.jsonl")
        with open(input_jsonl_file, "w", encoding="utf8") as input_file:
            input_file.writelines(test_jsonl)

        dry_runner = DryRunner(
            dry_run=input_jsonl_file,
            config_path=self.config_path,
            full_output=True,
            use_json=False,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert captured.out.count("------ PROCESSED EVENT ------") == 2
        assert "------ TRANSFORMED EVENTS: 2/2 ------" in captured.out

    def test_dry_run_print_custom_output(self, tmp_path, capsys):
        test_json = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {"param1": "username"},
            }
        }
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=self.config_path,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out
        assert "------ ALL PSEUDONYMS ------" in captured.out
        assert "------ ALL PRE-DETECTIONS ------" in captured.out

    def test_dry_run_prints_predetection(self, tmp_path, capsys):
        test_json = {
            "winlog": {
                "event_id": 123,
                "event_data": {"ServiceName": "VERY BAD"},
            }
        }
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=self.config_path,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out
        assert "------ ALL PSEUDONYMS ------" in captured.out
        assert "------ ALL PRE-DETECTIONS ------" in captured.out

    @mock.patch("logprep.processor.labeler.processor.Labeler.process", side_effect=BaseException)
    def test_dry_run_prints_errors(self, _, tmp_path, capsys):
        test_json = {
            "winlog": {
                "event_id": 123,
                "event_data": {"ServiceName": "VERY BAD"},
            }
        }
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=self.config_path,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ ERROR ------" in captured.out
