import re
from copy import deepcopy
from logging import getLogger

import pytest
pytest.importorskip('logprep.processor.pre_detector')

from logprep.processor.processor_factory_error import ProcessorFactoryError
from logprep.processor.pre_detector.factory import PreDetector, PreDetectorFactory

logger = getLogger()
rules_dir = 'tests/testdata/unit/pre_detector/rules'


@pytest.fixture()
def pre_detector():
    config = {
        'type': 'pre_detector',
        'rules': [rules_dir],
        'pre_detector_topic': 'pre_detector_alerts'
    }

    pre_detector = PreDetectorFactory.create('test-pre-detector', config, logger)
    return pre_detector


class TestPreDetector:

    uuid_pattern = re.compile(r'^[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}$')

    def test_perform_successful_pre_detection(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'winlog': {'event_id': 123, 'event_data': {'ServiceName': 'VERY BAD'}}}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_ONE_ID',
                    'title': 'RULE_ONE',
                    'severity': 'critical',
                    'mitre': ['attack.test1', 'attack.test2'],
                    'case_condition': 'directly',
                    'description': 'Test rule one',
                    'rule_filter': 'AND(winlog.event_id:"123", winlog.event_data.ServiceName:"VERY BAD")'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_perform_successful_pre_detection_with_host_name(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'host': {'name': 'Test hostname'},
                    'winlog': {'event_id': 123, 'event_data': {'ServiceName': 'VERY BAD'}}}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_ONE_ID',
                    'title': 'RULE_ONE',
                    'severity': 'critical',
                    'mitre': ['attack.test1', 'attack.test2'],
                    'case_condition': 'directly',
                    'host': {'name': 'Test hostname'},
                    'description': 'Test rule one',
                    'rule_filter': 'AND(winlog.event_id:"123", winlog.event_data.ServiceName:"VERY BAD")'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_perform_successful_pre_detection_with_same_existing_pre_detection(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'winlog': {'event_id': 123, 'event_data': {'ServiceName': 'VERY BAD'}}}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_ONE_ID',
                    'title': 'RULE_ONE',
                    'severity': 'critical',
                    'mitre': ['attack.test1', 'attack.test2'],
                    'case_condition': 'directly',
                    'description': 'Test rule one',
                    'rule_filter': 'AND(winlog.event_id:"123", winlog.event_data.ServiceName:"VERY BAD")'
                }
            ],
            'pre_detector_alerts')

        document['pre_detection_id'] = '11fdfc1f-8e00-476e-b88f-753d92af989c'
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_perform_successful_pre_detection_with_pre_detector_complex_rule_suceeds_msg_t1(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test1*xyz'}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_TWO_ID', 'title': 'RULE_TWO',
                    'severity': 'critical',
                    'mitre': [],
                    'case_condition': 'directly',
                    'description': 'Test rule two',
                    'rule_filter': 'AND(tags:"test", '
                                        'process.program:"test", '
                                        'OR(message:"test1*xyz", '
                                        'message:"test2*xyz"))'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_perform_successful_pre_detection_with_pre_detector_complex_rule_succeeds_msg_t2(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2Xxyz'}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_THREE_ID', 'title': 'RULE_THREE',
                    'severity': 'critical',
                    'mitre': [],
                    'case_condition': 'directly',
                    'description': 'Test rule three',
                    'rule_filter': 'AND(tags:"test2", '
                                        'process.program:"test", '
                                        'OR(message:"test1*xyz", '
                                        'message:"test2?xyz"))'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_perform_successful_pre_detection_with_two_rules(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'first_match': 'something', 'second_match': 'something'}
        expected = deepcopy(document)
        expected_detection_results = ([
            {
                'case_condition': 'directly',
                'id': 'RULE_ONE_ID',
                'mitre': ['attack.test1', 'attack.test2'],
                'description': 'Test two rules one',
                'rule_filter': '"first_match"',
                'severity': 'critical',
                'title': 'RULE_ONE'
            },
            {
                'case_condition': 'directly',
                'id': 'RULE_TWO_ID',
                'mitre': ['attack.test2', 'attack.test4'],
                'description': 'Test two rules two',
                'rule_filter': '"second_match"',
                'severity': 'suspicious',
                'title': 'RULE_TWO'
            }
            ], 'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_correct_star_wildcard_behavior(self, pre_detector):
        assert pre_detector.events_processed_count() == 0

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test3*xyz'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test3*xyz'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test3*xyzA'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test3*xyzA'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2*xyzA'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2*xyzA'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2xyz'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2xyz'}
        pre_detector.process(document)
        assert document != expected

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2Axyz'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2Axyz'}
        pre_detector.process(document)
        assert document != expected

        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2AAxyz'}
        expected = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'test2AAxyz'}
        pre_detector.process(document)
        assert document != expected

    def test_correct_questionmark_wildcard_behavior(self, pre_detector):
        assert pre_detector.events_processed_count() == 0

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test3*xyz'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test3*xyz'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test3*xyzA'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test3*xyzA'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2*xyzA'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2*xyzA'}
        pre_detector.process(document)
        assert document == expected

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2xyz'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2xyz'}
        pre_detector.process(document)
        assert document != expected

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2Axyz'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2Axyz'}
        pre_detector.process(document)
        assert document != expected

        document = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2AAxyz'}
        expected = {'tags': 'test2', 'process': {'program': 'test'}, 'message': 'test2AAxyz'}
        pre_detector.process(document)
        assert document == expected

    def test_ignores_case(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': 'TEST2*xyz'}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_TWO_ID', 'title': 'RULE_TWO', 'severity': 'critical', 'mitre': [],
                    'case_condition': 'directly',
                    'description': 'Test rule two',
                    'rule_filter': 'AND(tags:"test", process.program:"test", OR(message:"test1*xyz", message:"test2*xyz"))'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)

    def test_ignores_case_list(self, pre_detector):
        assert pre_detector.events_processed_count() == 0
        document = {'tags': 'test', 'process': {'program': 'test'}, 'message': ['TEST2*xyz']}
        expected = deepcopy(document)
        expected_detection_results = (
            [
                {
                    'id': 'RULE_TWO_ID', 'title': 'RULE_TWO', 'severity': 'critical', 'mitre': [],
                    'case_condition': 'directly',
                    'description': 'Test rule two',
                    'rule_filter': 'AND(tags:"test", process.program:"test", OR(message:"test1*xyz", message:"test2*xyz"))'
                }
            ],
            'pre_detector_alerts')
        detection_results = pre_detector.process(document)
        self._assert_equality_of_results(document, expected, detection_results, expected_detection_results)
        
    def _assert_equality_of_results(self, document, expected, detection_results, expected_detection_results):
        pre_detection_id = document.pop('pre_detection_id', None)

        assert pre_detection_id is not None
        assert self.uuid_pattern.search(pre_detection_id)
        assert document == expected

        for detection_result in detection_results[0]:
            result_pre_detection_id = detection_result.pop('pre_detection_id', None)
            assert result_pre_detection_id is not None
            assert pre_detection_id == result_pre_detection_id
        assert detection_results == expected_detection_results


class TestPreDetectorFactory:
    VALID_CONFIG = {
        'type': 'pre_detector',
        'rules': [rules_dir],
        'pre_detector_topic': 'pre_detector_alerts'
    }

    def test_create(self):
        assert isinstance(PreDetectorFactory.create('foo', self.VALID_CONFIG, logger), PreDetector)

    def test_check_configuration(self):
        PreDetectorFactory._check_configuration(self.VALID_CONFIG)
        for i in range(len(self.VALID_CONFIG)):
            cfg = deepcopy(self.VALID_CONFIG)
            cfg.pop(list(cfg)[i])
            with pytest.raises(ProcessorFactoryError):
                PreDetectorFactory._check_configuration(cfg)
