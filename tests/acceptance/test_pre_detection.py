# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-locals
import json
import re
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest
from deepdiff import DeepDiff

from tests.acceptance.util import get_default_logprep_config, get_test_output

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


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


# fmt: off
@pytest.mark.parametrize(
    "input_event, expected_output_event, expected_extra_output",
    [
        (
            {"@timestamp":"2019-08-02T09:46:20.000Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"event":{"kind":"event","code":6005,"created":"2019-08-02T09:55:11.996Z"},"ecs":{"version":"1.0.0"},"host":{"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1","architecture":"x86","os":{"version":"6.1","family":"windows","name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows"},"name":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"},"log":{"level":"information"},"message":"The Event log service was started.","winlog":{"provider_name":"EventLog","task":"","channel":"System","event_data":{"Binary":"E30708000500020009002E00140057010000000000000000"},"event_id":6005,"computer_name":"abcdefg1234","keywords":["Classic"],"record_id":11571,"api":"wineventlog"}},
            {"@timestamp":"2019-08-02T09:46:20.000Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"event":{"kind":"event","code":6005,"created":"2019-08-02T09:55:11.996Z"},"ecs":{"version":"1.0.0"},"host":{"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1","architecture":"x86","os":{"version":"6.1","family":"windows","name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows"},"name":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"},"log":{"level":"information"},"message":"The Event log service was started.","winlog":{"provider_name":"EventLog","task":"","channel":"System","event_data":{"Binary":"E30708000500020009002E00140057010000000000000000"},"event_id":6005,"computer_name":"abcdefg1234","keywords":["Classic"],"record_id":11571,"api":"wineventlog"}},
            None
        ),
        (
            {"@timestamp":"2019-07-30T14:38:16.352Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"event":{"code":7036,"created":"2019-08-02T09:55:11.996Z","kind":"event"},"agent":{"version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0"},"ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","hostname":"CLIENT1","architecture":"x86","os":{"name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4"},"log":{"level":"information"},"message":"The Software Protection service entered the stopped state.","winlog":{"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","event_id":1234,"task":"","api":"wineventlog","event_data":{"Binary":"7300700070007300760063002F0031000000","param1":"Software Protection","param2":"stopped"},"keywords":["Classic"],"provider_name":"Service Control Manager","record_id":11580,"channel":"System","computer_name":"abcdefg1234","process":{"thread":{"id":2808},"pid":436}}},
            {"@timestamp":"2019-07-30T14:38:16.352Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"event":{"code":7036,"created":"2019-08-02T09:55:11.996Z","kind":"event"},"agent":{"version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0"},"ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","hostname":"CLIENT1","architecture":"x86","os":{"name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4"},"log":{"level":"information"},"message":"The Software Protection service entered the stopped state.","winlog":{"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","event_id":1234,"task":"","api":"wineventlog","event_data":{"Binary":"7300700070007300760063002F0031000000","param1":"Software Protection","param2":"stopped"},"keywords":["Classic"],"provider_name":"Service Control Manager","record_id":11580,"channel":"System","computer_name":"abcdefg1234","process":{"thread":{"id":2808},"pid":436}}},
            [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "1cf39644-a632-4c42-a7b4-2896c4efffb5", "host": {"name": "CLIENT1"}, "@timestamp": "2019-07-30T14:38:16.352000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            {"@timestamp":"2019-08-02T09:46:41.906Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"host":{"name":"CLIENT1","os":{"name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1","architecture":"x86"},"agent":{"hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9"},"ecs":{"version":"1.0.0"},"winlog":{"channel":"System","provider_name":"Service Control Manager","record_id":11627,"event_id":1234,"api":"wineventlog","keywords":["Classic"],"computer_name":"abcdefg1234","process":{"pid":440,"thread":{"id":524}},"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","event_data":{"param1":"Wazuh","param2":"running","Binary":"4F0073007300650063005300760063002F0034000000"},"task":""},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:11.998Z"},"log":{"level":"information"},"message":"The Wazuh service entered the running state."},
            {"@timestamp":"2019-08-02T09:46:41.906Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"host":{"name":"CLIENT1","os":{"name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1","architecture":"x86"},"agent":{"hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9"},"ecs":{"version":"1.0.0"},"winlog":{"channel":"System","provider_name":"Service Control Manager","record_id":11627,"event_id":1234,"api":"wineventlog","keywords":["Classic"],"computer_name":"abcdefg1234","process":{"pid":440,"thread":{"id":524}},"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","event_data":{"param1":"Wazuh","param2":"running","Binary":"4F0073007300650063005300760063002F0034000000"},"task":""},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:11.998Z"},"log":{"level":"information"},"message":"The Wazuh service entered the running state."},
            [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "08d1aa6f-f508-464e-a13d-0b5da46b5bcc", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:46:41.906000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            {"@timestamp":"2019-08-02T09:46:54.583Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"provider_name":"Service Control Manager","computer_name":"abcdefg1234","provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","process":{"pid":440,"thread":{"id":1792}},"event_data":{"param1":"Portable Device Enumerator Service","param2":"running","Binary":"57005000440042007500730045006E0075006D002F0034000000"},"channel":"System","record_id":11638,"task":"","api":"wineventlog","event_id":1234,"keywords":["Classic"]},"event":{"code":7036,"created":"2019-08-02T09:55:11.999Z","kind":"event"},"agent":{"ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat"},"ecs":{"version":"1.0.0"},"host":{"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","name":"CLIENT1","hostname":"CLIENT1","architecture":"x86","os":{"platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0"}},"log":{"level":"information"},"message":"The Portable Device Enumerator Service service entered the running state."},
            {"@timestamp":"2019-08-02T09:46:54.583Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"provider_name":"Service Control Manager","computer_name":"abcdefg1234","provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","process":{"pid":440,"thread":{"id":1792}},"event_data":{"param1":"Portable Device Enumerator Service","param2":"running","Binary":"57005000440042007500730045006E0075006D002F0034000000"},"channel":"System","record_id":11638,"task":"","api":"wineventlog","event_id":1234,"keywords":["Classic"]},"event":{"code":7036,"created":"2019-08-02T09:55:11.999Z","kind":"event"},"agent":{"ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1","id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat"},"ecs":{"version":"1.0.0"},"host":{"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","name":"CLIENT1","hostname":"CLIENT1","architecture":"x86","os":{"platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional","kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0"}},"log":{"level":"information"},"message":"The Portable Device Enumerator Service service entered the running state."},
            [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "06d12743-01f0-4793-8a31-3815cfa31fc3", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:46:54.583000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            {"@timestamp":"2019-08-02T09:54:57.125Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"computer_name":"abcdefg1234","event_id":123,"record_id":11714,"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","channel":"System","task":"","api":"wineventlog","event_data":{"param2":"running","Binary":"41007500640069006F007300720076002F0034000000","param1":"Windows Audio"},"provider_name":"Service Control Manager 2","keywords":["Classic"],"process":{"pid":440,"thread":{"id":528}}},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:12.091Z"},"log":{"level":"information"},"message":"The Windows Audio service entered the running state.","ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","architecture":"x86","os":{"kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"}},
            {"@timestamp":"2019-08-02T09:54:57.125Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"computer_name":"abcdefg1234","event_id":123,"record_id":11714,"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","channel":"System","task":"","api":"wineventlog","event_data":{"param2":"running","Binary":"41007500640069006F007300720076002F0034000000","param1":"Windows Audio"},"provider_name":"Service Control Manager 2","keywords":["Classic"],"process":{"pid":440,"thread":{"id":528}}},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:12.091Z"},"log":{"level":"information"},"message":"The Windows Audio service entered the running state.","ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","architecture":"x86","os":{"kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"}},
            [{"pre_detector_topic": {"description": "", "id": "c46b8c22-41f5-4c45-b1a0-3fbe3a5c186d", "title": "RULE_TWO", "severity": "critical", "mitre": ["mitre2", "mitre3"], "case_condition": "directly", "rule_filter": 'winlog.event_id:"123"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
        (
            {"@timestamp":"2019-08-02T09:54:57.125Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"computer_name":"abcdefg1234","event_id":123,"record_id":11714,"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","channel":"System","task":"","api":"wineventlog","event_data":{"param2":"running","Binary":"41007500640069006F007300720076002F0034000000","param1":"Windows Audio"},"provider_name":"Service Control Manager","keywords":["Classic"],"process":{"pid":440,"thread":{"id":528}}},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:12.091Z"},"log":{"level":"information"},"message":"The Windows Audio service entered the running state.","ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","architecture":"x86","os":{"kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"}},
            {"@timestamp":"2019-08-02T09:54:57.125Z","@metadata":{"beat":"winlogbeat","type":"_doc","version":"7.2.0","topic":"wineventlog_raw"},"winlog":{"computer_name":"abcdefg1234","event_id":123,"record_id":11714,"provider_guid":"{555908d1-a6d7-4695-8e1e-26931d2012f4}","channel":"System","task":"","api":"wineventlog","event_data":{"param2":"running","Binary":"41007500640069006F007300720076002F0034000000","param1":"Windows Audio"},"provider_name":"Service Control Manager","keywords":["Classic"],"process":{"pid":440,"thread":{"id":528}}},"event":{"kind":"event","code":7036,"created":"2019-08-02T09:55:12.091Z"},"log":{"level":"information"},"message":"The Windows Audio service entered the running state.","ecs":{"version":"1.0.0"},"host":{"name":"CLIENT1","architecture":"x86","os":{"kernel":"6.1.7601.18741 (win7sp1_gdr.150202-1526)","build":"7601.0","platform":"windows","version":"6.1","family":"windows","name":"Windows 7 Professional"},"id":"19fc45ac-5890-4f96-81b1-50ed111c0ce4","hostname":"CLIENT1"},"agent":{"id":"0b755aca-0a9a-454a-9800-1979901962a0","version":"7.2.0","type":"winlogbeat","ephemeral_id":"de845cd9-5141-4c92-ad32-27a4518307e9","hostname":"CLIENT1"}},
            [{"pre_detector_topic": {"description": "", "id": "886a07aa-4c72-4fcb-a74a-b494443b3efd", "title": "RULE_ONE", "severity": "critical", "mitre": ["mitre1", "mitre2"], "case_condition": "directly", "rule_filter": 'winlog.provider_name:"Service Control Manager"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z"}},
             {"pre_detector_topic": {"description": "", "id": "c46b8c22-41f5-4c45-b1a0-3fbe3a5c186d", "title": "RULE_TWO", "severity": "critical", "mitre": ["mitre2", "mitre3"], "case_condition": "directly", "rule_filter": 'winlog.event_id:"123"', "pre_detection_id": "638cc0b3-b912-4220-8551-defea8ea139d", "host": {"name": "CLIENT1"}, "@timestamp": "2019-08-02T09:54:57.125000Z", "creation_timestamp": "2019-07-30T14:58:16.352Z"}}]
        ),
    ],
)
# fmt: on
def test_events_pre_detected_correctly(
    tmp_path: Path, input_event, expected_output_event, expected_extra_output
):
    input_file_path = tmp_path / "input.json"
    input_file_path.write_text(json.dumps(input_event))
    config = get_default_logprep_config(pipeline_config=pipeline, with_hmac=False)
    config.input["jsonl"]["documents_path"] = str(input_file_path)
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    logprep_output, logprep_extra_output, logprep_error_output = get_test_output(str(config_path))
    assert not logprep_error_output
    diff = DeepDiff(
        expected_output_event,
        logprep_output[0],  # pylint: disable=unsubscriptable-object
        exclude_paths="root['pre_detection_id']",
    )
    assert not diff, f"The expected output event and the logprep output differ: {diff}"
    if expected_extra_output is not None:
        # compare every expected extra output with every logprep extra output and search for match
        for expected_extra_out in expected_extra_output:
            has_matching_output = False
            for logprep_extra_out in logprep_extra_output:  # pylint: disable=not-an-iterable
                exclude_pre_detection_id_regex_path = re.compile(
                    r"root\['pre_detector_topic'\]\['pre_detection_id'\]"
                )
                exclude_creation_timestamp_regex_path = re.compile(
                    r"root\['pre_detector_topic'\]\['creation_timestamp'\]"
                )
                diff = DeepDiff(
                    expected_extra_out,
                    logprep_extra_out,
                    exclude_regex_paths=[
                        exclude_pre_detection_id_regex_path,
                        exclude_creation_timestamp_regex_path,
                    ],
                )
                if not diff:
                    has_matching_output = True
            assert has_matching_output, (
                f"The expected extra output doesn't have a matching logprep extra output\n"
                f"Logprep extra output: {logprep_extra_output}\n"
                f"Expected extra output: {expected_extra_output}"
            )
