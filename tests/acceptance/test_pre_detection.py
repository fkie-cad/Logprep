# pylint: disable=missing-docstring
from logprep.util.json_handling import dump_config_as_file, parse_jsonl
from tests.acceptance.util import *

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


pipeline = [
    {
        "pre_detector": {
            "type": "pre_detector",
            "outputs": [{"jsonl": "pre_detector_topic"}],
            "generic_rules": [],
            "specific_rules": ["tests/testdata/acceptance/pre_detector/rules/"],
            "tree_config": "tests/testdata/acceptance/pre_detector/tree_config.json",
        }
    },
]


def test_events_pre_detected_correctly(tmp_path):
    config = get_default_logprep_config(pipeline_config=pipeline, with_hmac=False)
    expected_output_file_name = "pre_detection_expected.jsonl"
    expected_output_path = path.join(
        "tests/testdata/acceptance/expected_result", expected_output_file_name
    )
    expected_output = parse_jsonl(expected_output_path)
    expected_logprep_outputs = [event for event in expected_output if "mitre" not in event.keys()]
    expected_logprep_extra_output = [
        event for event in expected_output if "pre_detector_topic" in event.keys()
    ]

    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)

    logprep_output, logprep_extra_output, logprep_error_output = get_test_output(config_path)
    assert len(logprep_error_output) == 0, "There shouldn't be any logprep errors"
    result_detections = get_difference_detections(logprep_output, expected_logprep_outputs)
    assert (
        result_detections["difference"][0] == result_detections["difference"][1]
    ), f"Missmatch in event at line {result_detections['event_line_no']}!"
    result_detections = get_difference_detections(
        logprep_extra_output, expected_logprep_extra_output
    )
    assert (
        result_detections["difference"][0] == result_detections["difference"][1]
    ), f"Missmatch in event at line {result_detections['event_line_no']}!"


def get_difference_detections(logprep_output, expected_logprep_output):
    for test_case_id, _ in enumerate(logprep_output):
        test_event = deepcopy(logprep_output[test_case_id])
        expected_event = deepcopy(expected_logprep_output[test_case_id])
        if "pre_detection_id" in test_event:
            del test_event["pre_detection_id"]
        if "pre_detection_id" in expected_logprep_output[test_case_id]:
            del expected_event["pre_detection_id"]
        if "pre_detector_topic" in test_event:
            del test_event["pre_detector_topic"]["pre_detection_id"]
        if "pre_detector_topic" in expected_logprep_output[test_case_id]:
            del expected_event["pre_detector_topic"]["pre_detection_id"]
        difference = recursive_compare(test_event, expected_event)
        if difference:
            return {"event_line_no": test_case_id, "difference": difference}
    return {"event_line_no": None, "difference": (None, None)}
