# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=attribute-defined-outside-init
import json
from pathlib import Path

import pytest
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


# fmt: off
@pytest.mark.parametrize(
    "input_line, expected_extra_output",
    [
        (
            1, [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "1cf39644-a632-4c42-a7b4-2896c4efffb5", "host": {"name": "CLIENT1"}, "@timestamp": "2019-07-30T14:38:16.352000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            2, [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "08d1aa6f-f508-464e-a13d-0b5da46b5bcc", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:46:41.906000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            3, [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "06d12743-01f0-4793-8a31-3815cfa31fc3", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:46:54.583000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            4, [{"pre_detector_topic": {"description": "", "id": "c46b8c22-41f5-4c45-b1a0-3fbe3a5c186d", "title": "RULE_TWO", "severity": "critical", "mitre": ["mitre2", "mitre3"], "case_condition": "directly", "rule_filter": 'winlog.event_id:"123"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            5, [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z"}},
             {"pre_detector_topic": {"description": "", "id": "c46b8c22-41f5-4c45-b1a0-3fbe3a5c186d", "title": "RULE_TWO", "severity": "critical", "mitre": ["mitre2", "mitre3"], "case_condition": "directly", "rule_filter": 'winlog.event_id:"123"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
    ],
)
# fmt: on
def test_events_pre_detected_return_extra_output(input_line, expected_extra_output, tmp_path: Path):
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = tmp_path / "generated_config.yml"

    input_file_path = Path(config.input["jsonl"]["documents_path"])
    input_data = map(json.loads, input_file_path.read_text("utf8").splitlines())
    input_tmp_path = tmp_path / "input.json"
    config.input["jsonl"]["documents_path"] = str(input_tmp_path)
    config_path.write_text(config.as_yaml())
    input_tmp_path.write_text(json.dumps(list(input_data)[input_line]))

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
    ), f"No matching logprep extra output found.\nExpected: {expected_extra_output}"
