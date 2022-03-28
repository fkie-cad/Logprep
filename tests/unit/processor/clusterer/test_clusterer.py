import copy
from unittest import mock
from logging import getLogger

import pytest
pytest.importorskip('logprep.processor.clusterer')

from logprep.processor.clusterer.rule import ClustererRule
from logprep.processor.clusterer.factory import Clusterer, ClustererFactory
from logprep.processor.base.processor import BaseProcessor, ProcessingWarning
from logprep.processor.processor_factory_error import ProcessorFactoryError

logger = getLogger()


@pytest.fixture
def clusterer():
    return Clusterer('Test Clusterer Name', 'tests/testdata/unit/shared_data/tree_config.json',
                     logger)


class TestClusterer:
    def test_is_a_processor_implementation(self, clusterer):
        assert isinstance(clusterer, BaseProcessor)

    def test_describe(self, clusterer):
        assert clusterer.describe() == 'Clusterer (Test Clusterer Name)'

    def test_events_processed_count(self, clusterer):
        assert clusterer.ps.processed_count == 0
        document = {'foo': 'bar'}
        for idx in range(1, 11):
            try:
                clusterer.process(document)
            except ProcessingWarning:
                pass
            assert clusterer.ps.processed_count == idx

    def test_has_tag_clusterable(self, clusterer):
        # Sample without PRI, since PRI makes a log clusterable irrespective of the tag
        sample_syslog_without_pri = {
            'severity_label': 'Informational',
            'pid': '1339',
            'host': '172.16.0.2',
            'timestamp': '2019-02-04T14:06:00.010548+01:00',
            'logsource': 'internalserver',
            'priority': 30,
            '@timestamp': '2019-02-04T13:06:00.010Z',
            'message': 'Listen normally on 5 lo ::1 UDP 123\n',
            'program': 'ntpd',
            'syslog': {
                'facility_label': 'system',
                'priority': 30,
                'severity_label': 'Informational'
            },
            '@version': '1',
            'tags': ['clusterable'],
            'timestamp8601': '2019-02-04T14:06:00.010548+01:00'}
        sample_winevtlog = {
            'type': 'wineventlog',
            'winlog': {
                'event_data': {
                    'param1': 'Windows Defender',
                    'param2': 'running',
                    'Binary': '570069006E0044006500660065006E0064002F0034000000'}},
            'process_id': 440,
            'provider_guid': '{555908d1-a6d7-4695-8e1e-26931d2012f4}',
            'beat': {
                'name': 'CLIENT1',
                'version': '6.3.1',
                'hostname': 'CLIENT1'},
            'record_number': '11234',
            'host': {
                'name': 'CLIENT1'},
            'tags': [
                'beats_input_codec_plain_applied'],
            'keywords': [
                'Classic'],
            'level': 'Information',
            'thread_id': 560,
            'log_name': 'System',
            '@timestamp': '2019-02-04T13:09:56.036Z',
            'computer_name': 'CLIENT1.breach.local',
            'message': 'The Windows Defender service entered the running state.',
            'source_name': 'Service Control Manager',
            '@version': '1',
            'event_id': 7036}
        invalid_syslog_with_missing_tag = {
            'message': 'Listen normally on 5 lo ::1 UDP 123\n'
        }
        invalid_syslog_with_none_message = {
            'message': None,
            'tags': ['clusterable']
        }

        assert clusterer._is_clusterable(sample_syslog_without_pri)
        assert not clusterer._is_clusterable(sample_winevtlog)
        assert not clusterer._is_clusterable(invalid_syslog_with_missing_tag)
        assert not clusterer._is_clusterable(invalid_syslog_with_none_message)

    @mock.patch('logprep.processor.clusterer.processor.Clusterer._is_clusterable')
    @mock.patch('logprep.processor.clusterer.processor.Clusterer._cluster')
    def test_only_clusterable_logs_are_clustered(
            self, mock_cluster, mock_is_clusterable, clusterer):
        mock_is_clusterable.return_value = False
        clusterer.process({})
        mock_cluster.assert_not_called()

        mock_is_clusterable.return_value = True
        clusterer.process({})
        mock_cluster.assert_called_once()

    def test_syslog_has_severity_and_facility(self, clusterer):
        valid_syslog_with_facility_and_severity = {
            'syslog': {
                'facility': 3
            },
            'event': {
                'severity': 6
            },
            'message': 'Listen normally on 5 lo ::1 UDP 123\n'
        }
        invalid_syslog_with_missing_severity_and_facility = {
            'message': 'Listen normally on 5 lo ::1 UDP 123\n'
        }

        assert clusterer._syslog_has_pri(valid_syslog_with_facility_and_severity)
        assert not clusterer._syslog_has_pri(invalid_syslog_with_missing_severity_and_facility)

    def test_clusterable_field_determines_if_clusterable(self, clusterer):
        """Check if clusterable has precedence over the existence of facility and severity"""
        log_with_clusterable_field_equals_true = {
            'message': 'Listen normally on 5 lo ::1 UDP 123\n',
            'clusterable': True
        }
        log_with_clusterable_field_equals_false = {
            'message': 'Listen normally on 5 lo ::1 UDP 123\n',
            'clusterable': False
        }
        valid_syslog_with_clusterable_field_equals_true = {
            'syslog': {
                'facility': 3
            },
            'event': {
                'severity': 6
            },
            'message': 'Listen normally on 5 lo ::1 UDP 123\n',
            'clusterable': True
        }
        syslog_with_clusterable_field_equals_false = {
            'syslog': {
                'facility': 3
            },
            'event': {
                'severity': '6'
            },
            'message': 'Listen normally on 5 lo ::1 UDP 123\n',
            'clusterable': False
        }

        assert clusterer._is_clusterable(log_with_clusterable_field_equals_true)
        assert clusterer._is_clusterable(valid_syslog_with_clusterable_field_equals_true)
        assert not clusterer._is_clusterable(log_with_clusterable_field_equals_false)
        assert not clusterer._is_clusterable(syslog_with_clusterable_field_equals_false)

    def test_rule_tests(self, clusterer):
        rule_definition = {
            'filter': 'message',
            'clusterer': {
                'target': 'message',
                'pattern': r'test (signature) test',
                'repl': r'<+>\1</+>'
            },
            'description': 'insert a description text',
            'tests': {
                'raw': 'test signature test',
                'result': '<+>signature</+>'
            }
        }

        rule = ClustererRule._create_from_dict(rule_definition)
        clusterer._rules.append(rule)

        results = clusterer.test_rules()
        for rule_results in results.values():
            for result, expected in rule_results:
                assert result == expected

    def test_cluster(self, clusterer):
        rule_definition = {
            'filter': 'message',
            'clusterer': {
                'target': 'message',
                'pattern': r'test (signature) test',
                'repl': r'<+>\1</+>'
            },
            'description': 'insert a description text',
            'tests': {
                'raw': 'test signature test',
                'result': '<+>signature</+>'
            }
        }

        expected = {
            'cluster_signature': 'signature',
            'message': 'test signature test'
        }

        document = {'message': 'test signature test'}
        rule = ClustererRule._create_from_dict(rule_definition)
        clusterer._cluster(document, [rule])

        assert document == expected


class TestClustererFactory:
    VALID_CONFIG = {
        'type': 'clusterer',
        'output_field_name': 'cluster_signature',
        'rules': 'test_path'}

    def test_create(self):
        assert isinstance(ClustererFactory.create('foo', self.VALID_CONFIG, logger), Clusterer)

    def test_check_configuration(self):
        ClustererFactory._check_configuration(self.VALID_CONFIG)
        for i in range(len(self.VALID_CONFIG)):
            cfg = copy.deepcopy(self.VALID_CONFIG)
            cfg.pop(list(cfg)[i])
            with pytest.raises(ProcessorFactoryError):
                ClustererFactory._check_configuration(cfg)
