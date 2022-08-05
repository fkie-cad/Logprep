# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import json
import logging
import os

from logprep.util.rule_dry_runner import DryRunner


class TestRunLogprep:
    def test_dry_run_accepts_json_as_input(self, tmp_path, capsys):
        config = "tests/testdata/config/config-dry-run.yml"
        test_json = {"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=config,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_json_in_list_as_input(self, tmp_path, capsys):
        config = "tests/testdata/config/config-dry-run.yml"
        test_json = [{"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}]
        input_json_file = os.path.join(tmp_path, "test_input.json")
        with open(input_json_file, "w", encoding="utf8") as input_file:
            json.dump(test_json, input_file)

        dry_runner = DryRunner(
            dry_run=input_json_file,
            config_path=config,
            full_output=True,
            use_json=True,
            logger=logging.getLogger("test-logger"),
        )
        dry_runner.run()

        captured = capsys.readouterr()
        assert "------ PROCESSED EVENT ------" in captured.out
        assert "------ TRANSFORMED EVENTS: 1/1 ------" in captured.out

    def test_dry_run_accepts_jsonl_as_input(self, tmp_path, capsys):
        config = "tests/testdata/config/config-dry-run.yml"
        test_jsonl = [
            '{"winlog": {"event_id": 1111, "event_data": {"test2": "fancy data"}}}\n',
            '{"winlog": {"event_id": 1111, "event_data": {"test2": "more fancy data"}}}',
        ]
        input_jsonl_file = os.path.join(tmp_path, "test_input.jsonl")
        with open(input_jsonl_file, "w", encoding="utf8") as input_file:
            input_file.writelines(test_jsonl)

        dry_runner = DryRunner(
            dry_run=input_jsonl_file,
            config_path=config,
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
        config = "tests/testdata/config/config-dry-run.yml"
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
            config_path=config,
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
