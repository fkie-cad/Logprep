# pylint: disable=missing-docstring
from tests.acceptance.util import *
from logprep.util.helper import recursive_compare
from logprep.util.json_handling import dump_config_as_file, parse_jsonl

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


pipeline = [
    {
        "pre_detector": {
            "type": "pre_detector",
            "pre_detector_topic": "pre_detector_topic",
            "generic_rules": ["tests/testdata/acceptance/pre_detector/rules/"],
            "specific_rules": ["tests/testdata/acceptance/pre_detector/rules/"],
            "tree_config": "tests/testdata/acceptance/pre_detector/tree_config.json",
        }
    },
]


def test_events_pre_detected_correctly(tmp_path):
    config = get_default_logprep_config(pipeline_config=pipeline, with_hmac=False)
    expected_output = "pre_detection_expected.jsonl"
    expected_output_path = path.join("tests/testdata/acceptance/expected_result", expected_output)

    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)

    test_output, _, _ = get_test_output(config_path)
    store_latest_test_output(expected_output, test_output)

    expected_output = parse_jsonl(expected_output_path)

    test_output_documents = [event for event in test_output if "mitre" not in event.keys()]
    expected_output_documents = [event for event in expected_output if "mitre" not in event.keys()]

    result_detections = get_difference_detections(test_output_documents, expected_output_documents)
    assert (
        result_detections["difference"][0] == result_detections["difference"][1]
    ), f"Missmatch in event at line {result_detections['event_line_no']}!"

    test_output_detections = [event for event in test_output if "mitre" in event.keys()]
    expected_output_detections = [event for event in expected_output if "mitre" in event.keys()]

    result_detections = get_difference_detections(
        test_output_detections, expected_output_detections
    )
    assert (
        result_detections["difference"][0] == result_detections["difference"][1]
    ), f"Missmatch in event at line {result_detections['event_line_no']}!"


def get_difference_detections(test_output, expected_output):
    for x, _ in enumerate(test_output):
        test_event = deepcopy(test_output[x])
        _ = test_event.pop("pre_detection_id", None)
        _ = expected_output[x].pop("pre_detection_id", None)
        expected_event = deepcopy(expected_output[x])
        difference = recursive_compare(test_event, expected_event)
        if difference:
            return {"event_line_no": x, "difference": difference}
    return {"event_line_no": None, "difference": (None, None)}
