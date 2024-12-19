# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import json
import logging
import os
import tempfile
from pathlib import Path

from logprep.util.configuration import Configuration
from logprep.util.rule_dry_runner import DryRunner


class TestRunLogprep:
    def setup_method(self):
        config = """
        process_count: 1
        timeout: 0.1
        pipeline:
          - dissector:
              type: dissector
              rules:
                - tests/testdata/unit/dissector
          - labelername:
              type: labeler
              schema: tests/testdata/unit/labeler/schemas/schema3.json
              include_parent_labels: true
              rules:
                - tests/testdata/unit/labeler/rules
          - pseudonymizer:
              type: pseudonymizer
              pubkey_analyst: tests/testdata/unit/pseudonymizer/example_analyst_pub.pem
              pubkey_depseudo: tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem
              regex_mapping: tests/testdata/unit/pseudonymizer/regex_mapping.yml
              hash_salt: a_secret_tasty_ingredient
              outputs:
                - kafka_output: pseudonyms
              rules:
                - tests/testdata/unit/pseudonymizer/rules
              max_cached_pseudonyms: 1000000
          - predetectorname:
              type: pre_detector
              rules:
                - tests/testdata/unit/pre_detector/rules
              outputs:
                - kafka_output: sre_topic
          - selective_extractor:
              type: selective_extractor
              rules:
                - filter: message
                  selective_extractor:
                    source_fields: ["field1", "field2"]
                    outputs:
                        - kafka_output: topic
                  description: my reference rule
        input:
            kafka_output:
                type: dummy_input
                documents: []
        output:
            kafka_output:
                type: dummy_output
        """
        self.config_path = Path(tempfile.gettempdir()) / "dry-run-config.yml"
        self.config_path.write_text(config)
        self.config = Configuration.from_sources([str(self.config_path)])

    def teardown_method(self):
        os.remove(self.config_path)

    def test_dry_run_accepts_json_as_input(self, tmp_path, capsys):
        test_json = {"message": "123 456"}
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            input_file_path=input_json_file,
            config=self.config,
            full_output=True,
            use_json=True,
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert captured.err == ""
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_json_in_list_as_input(self, tmp_path, capsys):
        test_json = [{"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}]
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            input_file_path=input_json_file,
            config=self.config,
            full_output=True,
            use_json=True,
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert captured.err == ""
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_jsonl_as_input(self, tmp_path, capsys):
        test_jsonl = ['{"message": "123 456"}\n', '{"message": "789 012"}']
        input_jsonl_file = os.path.join(tmp_path, "test_input.jsonl")
        with open(input_jsonl_file, "w", encoding="utf8") as input_file:
            input_file.writelines(test_jsonl)

        dry_runner = DryRunner(
            input_file_path=input_jsonl_file,
            config=self.config,
            full_output=True,
            use_json=False,
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert captured.err == ""
        assert "------ PROCESSED EVENT ------" in captured.out
        assert captured.out.count("------ PROCESSED EVENT ------") == 2
        assert "------ TRANSFORMED EVENTS: 2/2 ------" in captured.out

    def test_dry_run_print_custom_output(self, tmp_path, capsys):
        test_json = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {"param1": "username"},
            },
            "message": "some message",
            "field1": "field for the selective extractor",
        }
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            input_file_path=input_json_file,
            config=self.config,
            full_output=True,
            use_json=True,
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out
        assert "------ CUSTOM OUTPUTS ------" in captured.out

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
            input_file_path=input_json_file,
            config=self.config,
            full_output=True,
            use_json=True,
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert captured.err == ""
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out
        assert "------ CUSTOM OUTPUTS ------" in captured.out
