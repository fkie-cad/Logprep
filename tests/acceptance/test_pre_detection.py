# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=attribute-defined-outside-init
import json
from pathlib import Path

import pytest
import yaml
from deepdiff import DeepDiff

from tests.acceptance.util import (
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    wait_for_output,
)


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)


pipeline = [
    {
        "pre_detector": {
            "type": "pre_detector",
            "outputs": [{"jsonl": "pre_detector_topic"}],
            "rules": ["tests/testdata/acceptance/pre_detector/rules/"],
            "tree_config": "tests/testdata/acceptance/pre_detector/tree_config.json",
        }
    },
]


def load_test_data():
    yaml_path = Path(
        "tests/testdata/input_logdata/kafka_raw_event_for_pre_detector_extra_output.yml"
    )
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))


def test_events_pre_detected_runs_without_error(tmp_path: Path):
    config = get_default_logprep_config(pipeline, with_hmac=False)
    input_file_path = tmp_path / "input.json"
    config.input["jsonl"]["documents_path"] = str(input_file_path)
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Startup complete")
    stop_logprep(proc)


def test_events_pre_detected_correctly(tmp_path: Path):
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())

    output_path = Path(config.output["jsonl"]["output_file"])
    input_file_path = Path(config.input["jsonl"]["documents_path"])

    proc = start_logprep(config_path)
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)

    assert output_path.read_text("utf8"), "output is not empty"

    output_data = map(json.loads, output_path.read_text("utf8").splitlines())
    input_data = map(json.loads, input_file_path.read_text("utf8").splitlines())

    for out, inp in zip(output_data, input_data):
        diff = DeepDiff(
            out,
            inp,
            exclude_paths="root['pre_detection_id']",
        )
        assert not diff, f"The expected output event and the logprep output differ: {diff}"


def test_events_pre_detected_return_no_extra_output(tmp_path: Path):
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = tmp_path / "generated_config.yml"

    input_file_path = Path(config.input["jsonl"]["documents_path"])
    input_data = map(json.loads, input_file_path.read_text("utf8").splitlines())

    input_tmp_path = tmp_path / "input.json"
    config.input["jsonl"]["documents_path"] = str(input_tmp_path)
    config_path.write_text(config.as_yaml())
    input_tmp_path.write_text(json.dumps(list(input_data)[0]))

    proc = start_logprep(config_path)
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)

    output_extra_path = Path(config.output["jsonl"]["output_file_custom"])
    assert not output_extra_path.read_text("utf8").strip()


@pytest.mark.parametrize("data", load_test_data())
def test_events_pre_detected_return_extra_output(data, tmp_path: Path):
    input_value = data["input_line"]
    expected_extra_output = data["expected_output"]

    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = tmp_path / "generated_config.yml"

    input_tmp_path = tmp_path / "input.json"
    config.input["jsonl"]["documents_path"] = str(input_tmp_path)
    config_path.write_text(config.as_yaml())
    input_tmp_path.write_text(input_value)

    proc = start_logprep(config_path)
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)

    output_extra_path = Path(config.output["jsonl"]["output_file_custom"])
    output_extra_data = map(json.loads, output_extra_path.read_text("utf8").splitlines())
    exclude_paths = {
        "root['pre_detector_topic']['pre_detection_id']",
        "root['pre_detector_topic']['creation_timestamp']",
    }

    assert any(
        not DeepDiff(expected, output, exclude_paths=exclude_paths, ignore_order=True)
        for output in output_extra_data
        for expected in expected_extra_output
    ), f"No matching logprep extra output found. \nExpected: {expected_extra_output}"
