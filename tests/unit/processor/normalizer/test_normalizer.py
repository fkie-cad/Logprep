import pytest
pytest.importorskip('logprep.processor.normalizer')

import copy
from logging import getLogger

from logprep.processor.normalizer.factory import Normalizer, NormalizerFactory
from logprep.processor.normalizer.rule import (NormalizerRule, InvalidNormalizationDefinition,
                                               InvalidGrokDefinition)
from logprep.processor.processor_factory_error import ProcessorFactoryError

from logprep.processor.normalizer.exceptions import NormalizerError
from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning

logger = getLogger()
specific_rules_dir = ['tests/testdata/unit/normalizer/rules/specific/']
generic_rules_dir = ['tests/testdata/unit/normalizer/rules/generic/']
cap_group_regex_mapping = 'tests/testdata/unit/normalizer/normalizer_regex_mapping.yml'
html_replace_fields = 'tests/testdata/unit/normalizer/html_replace_fields.yml'


@pytest.fixture()
def normalizer():
    return Normalizer('Test Normalizer Name', specific_rules_dir, generic_rules_dir, None, logger,
                      regex_mapping=cap_group_regex_mapping, html_replace_fields=html_replace_fields)


class TestNormalizer:
    @staticmethod
    def _load_specific_rule(normalizer, rule):
        specific_rule = NormalizerRule._create_from_dict(rule)
        normalizer._specific_tree.add_rule(specific_rule, logger)

    def test_is_a_processor_implementation(self, normalizer):
        assert isinstance(normalizer, RuleBasedProcessor)

    def test_describe(self, normalizer):
        assert normalizer.describe() == 'Normalizer (Test Normalizer Name)'

    def test_events_processed_count(self, normalizer):
        assert normalizer.events_processed_count() == 0
        document = {'foo': 'bar'}
        for i in range(1, 11):
            try:
                normalizer.process(document)
            except ProcessingWarning:
                pass
            assert normalizer.events_processed_count() == i

    def test_process_normalized_field_already_exists_with_same_content(self, normalizer):
        document = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1234,
                'event_data': {
                    'test_normalize': 'Existing and normalized have the same value'
                },
                'test_normalized': {
                    'something': 'Existing and normalized have the same value'
                }
            }
        }
        try:
            normalizer.process(document)
        except ProcessingWarning:
            pytest.fail('Normalization over an existing field with the same value as the normalized'
                        ' field should not raise a ProcessingWarning!')

        assert document['test_normalized']['something'] == 'Existing and normalized have the same value'

    def test_process_normalized_field_already_exists_with_different_content(self, normalizer):
        document = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1234,
                'event_data': {
                    'test_normalize': 'I am new and want to be normalized!'
                }
            },
            'test_normalized': {
                'something': 'I already exist but I am different!'
            }
        }
        with pytest.raises(ProcessingWarning,
                           match=r'The following fields already existed and were not '
                                 r'overwritten by the Normalizer: test_normalized.something\)'):
            normalizer.process(document)

        assert document['test_normalized']['something'] == 'I already exist but I am different!'

    def test_apply_windows_rules_catch_all(self, normalizer):
        document = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1234,
                'event_data': {
                    'test_normalize': 'foo'
                }
            }
        }
        normalizer.process(document)
        assert document['test_normalized']['something'] == 'foo'

    def test_apply_windows_rules_for_specific_event_id(self, normalizer):
        document = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1111,
                'event_data': {
                    'test1': 'foo'
                }
            }
        }
        normalizer.process(document)
        assert document['test_normalized']['test1'] == 'foo'

        document = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1112,
                'event_data': {
                    'test1': 'foo'
                }
            }
        }
        normalizer.process(document)
        assert 'test1' not in document.get('test_normalized', dict())

    def test_field_exists(self, normalizer):
        normalizer._event = {
            'host': {
                'user': {
                    'name': 'foo'}}}
        assert normalizer._field_exists('host')
        assert normalizer._field_exists('host.user')
        assert normalizer._field_exists('host.user.name')
        assert not normalizer._field_exists('foo')
        assert not normalizer._field_exists('user')
        assert not normalizer._field_exists('user.name')

    def test_add_field_without_conflicts(self, normalizer):
        normalizer._event = {
            'host': {
                'ip': '127.0.0.1'},
            'client': {
                'port': 22222}}
        normalizer._add_field('foo.bar.baz', 1234)
        normalizer._add_field('host.user.name', 'admin')
        normalizer._add_field('client.address', 'localhost')
        assert normalizer._event == {
            'foo': {
                'bar': {
                    'baz': 1234}},
            'host': {
                'ip': '127.0.0.1',
                'user': {
                    'name': 'admin'}},
            'client': {
                'address': 'localhost',
                'port': 22222}}
        assert not normalizer._conflicting_fields

    def test_add_field_with_conflicts(self, normalizer):
        normalizer._event = {
            'host': 'localhost'}
        normalizer._add_field('host.user.name', 'admin')
        assert normalizer._conflicting_fields == ['host.user.name']

    def test_normalization_from_specific_rules(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1111,
                'event_data': {
                    'param1': 'Do not normalize me!',
                    'test1': 'Normalize me!'
                }
            }
        }

        normalizer.process(event)

        assert event['winlog']['event_data']['param1'] == 'Do not normalize me!'
        assert event['test_normalized']['test1'] == 'Normalize me!'

    def test_normalization_from_specific_rule_with_multiple_matching_fields(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 2222,
                'event_data': {
                    'param1': 'Do not normalize me!',
                    'Test1': 'Normalize me.',
                    'Test2': 'Normalize me!'
                }
            }
        }

        normalizer.process(event)

        assert event['winlog']['event_data']['param1'] == 'Do not normalize me!'
        assert event['test_normalized']['test']['field1'] == 'Normalize me.'
        assert event['test_normalized']['test']['field2'] == 'Normalize me!'

    def test_normalization_from_generic_rules(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 1234,
                'event_data': {
                    'param1': 'Do not normalize me!',
                    'test1': 'Normalize me!'
                }
            }
        }

        normalizer.process(event)

        assert event['winlog']['event_data']['param1'] == 'Do not normalize me!'
        assert event['test_normalized']['something'] == 'Normalize me!'

    def test_normalize_with_invalid_list_fails(self, normalizer):
        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.invalid_normalization': [
                    'I am normalized!',
                    ''
                ]
            }
        }

        with pytest.raises(InvalidNormalizationDefinition):
            self._load_specific_rule(normalizer, rule)

    def test_normalize_full_field_with_regex_succeeds(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': 'Source value'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': [
                    'I am normalized!',
                    'RE_FULL_CAP',
                    r'\g<ALL>'
                ]
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event['I am normalized!'] == 'Source value'

    def test_normalize_full_field_with_regex_extraction_succeeds(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': 'xyz Only this! xyz'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': [
                    'I am normalized!',
                    'RE_ONLY_THIS_CAP',
                    r'\g<ONLY_THIS>'
                ]
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event['I am normalized!'] == 'Only this!'

    def test_normalize_full_field_with_non_matching_regex(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': 'Keep it as is!'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': [
                    'I am normalized!',
                    r'no match',
                    r'does not matter'
                ]
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event['I am normalized!'] == 'Keep it as is!'

    def test_normalize_full_field_with_regex_rearrange_succeeds(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': 'Second comes not before First'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': [
                    'I am normalized!',
                    'RE_SWITCH_CAP',
                    r'\g<FIRST> comes before \g<SECOND>'
                ]
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event['I am normalized!'] == 'First comes before Second'

    def test_normalization_from_grok(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBER:port:int}'}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip') == '123.123.123.123'
        assert event.get('port') == 1234

    def test_normalization_from_grok_match_only_exact(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': 'foo 123.123.123.123 1234 bar'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBER:port:int}'}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip') is None
        assert event.get('port') is None

    def test_normalization_from_grok_does_not_match(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBER:port:int}'}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip') is None
        assert event.get('port') is None

    def test_normalization_from_grok_list_match_first_matching(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': [
                    '%{IP:some_ip_1} %{NUMBER:port_1:int}',
                    '%{IP:some_ip_2} %{NUMBER:port_2:int}',
                ]}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip_1') == '123.123.123.123'
        assert event.get('port_1') == 1234
        assert event.get('some_ip_2') is None
        assert event.get('port_2') is None

    def test_normalization_from_grok_list_match_first_matching_after_skipping_non_matching(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234 bar'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': [
                    '%{IP:some_ip_1} %{NUMBER:port_1:int} foo',
                    '%{IP:some_ip_2} %{NUMBER:port_2:int} bar',
                ]}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip_1') is None
        assert event.get('port_1') is None
        assert event.get('some_ip_2') == '123.123.123.123'
        assert event.get('port_2') == 1234

    def test_normalization_from_grok_list_match_none(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': [
                    '%{IP:some_ip_1} %{NUMBER:port_1:int} foo',
                    '%{IP:some_ip_2} %{NUMBER:port_2:int} bar',
                ]}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip_1') is None
        assert event.get('port_1') is None
        assert event.get('some_ip_2') is None
        assert event.get('port_2') is None

    def test_normalization_from_nested_grok(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 555 1234 %ttss 11'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': r'%{IP:[parent][some_ip]} \w+ %{NUMBER:[parent][port]:int} %[ts]+ %{NUMBER:test:int}'}
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('test') == 11
        assert event.get('parent')
        assert event['parent'].get('some_ip') == '123.123.123.123'
        assert event['parent'].get('port') == 1234

    def test_normalization_from_grok_with_custom_patterns(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123456 Test other file!'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{CUSTOM_PATTERN_123456:custom_123456} %{CUSTOM_PATTERN_Test:custom_Test} %{CUSTOM_PATTERN_OTHER_FILE:custom_other_file}'}
            }
        }

        with pytest.raises(InvalidGrokDefinition):
            self._load_specific_rule(normalizer, rule)

        NormalizerRule.additional_grok_patterns = 'tests/testdata/unit/normalizer/additional_grok_patterns'
        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('custom_123456') == '123456'
        assert event.get('custom_Test') == 'Test'
        assert event.get('custom_other_file') == 'other file!'

    def test_normalization_from_grok_and_norm_result(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBER:port:int}'},
                'some_ip': 'some.ip'
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)
        
        assert event.get('some_ip') == '123.123.123.123'
        assert event.get('port') == 1234
        assert event.get('some')
        assert event['some'].get('ip') == '123.123.123.123'

    def test_normalization_from_grok_onto_existing(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:winlog} %{NUMBER:port:int}'}
            }
        }

        self._load_specific_rule(normalizer, rule)

        with pytest.raises(ProcessingWarning,
                           match=r'The following fields already existed and were not '
                                 r'overwritten by the Normalizer: winlog\)'):
            normalizer.process(event)

    def test_incorrect_grok_identifier_definition(self, normalizer):
        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'groks': '%{IP:some_ip} %{NUMBER:port:int}'}
            }
        }

        with pytest.raises(InvalidNormalizationDefinition):
            self._load_specific_rule(normalizer, rule)

    def test_incorrect_grok_definition(self, normalizer):
        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBA:port:int}'}
            }
        }

        with pytest.raises(InvalidGrokDefinition):
            self._load_specific_rule(normalizer, rule)

    def test_normalization_from_timestamp_berlin_to_utc(self, normalizer):
        expected = {
            '@timestamp': '1999-12-12T11:12:22Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'Europe/Berlin',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_grok_with_timestamp_normalization(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234 1999 12 12 - 12:12:22'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {'grok': '%{IP:some_ip} %{NUMBER:port:int} %{CUSTOM_TIMESTAMP:some_timestamp_utc}'},
                'some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        NormalizerRule.additional_grok_patterns = 'tests/testdata/unit/normalizer/additional_grok_patterns'
        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip') == '123.123.123.123'
        assert event.get('port') == 1234
        assert event.get('@timestamp') == '1999-12-12T12:12:22Z'

    def test_normalization_from_grok_with_timestamp_normalization_and_timestamp_does_not_exist(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'normalize me!': '123.123.123.123 1234'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.normalize me!': {
                    'grok': [
                        '%{IP:some_ip} %{NUMBER:port:int} %{CUSTOM_TIMESTAMP:some_timestamp_utc}',
                        '%{IP:some_ip} %{NUMBER:port:int}']},
                'some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        NormalizerRule.additional_grok_patterns = 'tests/testdata/unit/normalizer/additional_grok_patterns'
        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event.get('some_ip') == '123.123.123.123'
        assert event.get('port') == 1234
        assert event.get('@timestamp') is None

    def test_normalization_from_timestamp_same_timezones(self, normalizer):
        expected = {
            '@timestamp': '1999-12-12T12:12:22Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_timestamp_utc_to_berlin(self, normalizer):
        expected = {
            '@timestamp': '1999-12-12T13:12:22+01:00',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'Europe/Berlin'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_ISO8601_timestamp(self, normalizer):
        expected = {
            '@timestamp': '2020-01-03T14:04:05.879000Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '2020-01-03T14:04:05.879Z'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '2020-01-03T14:04:05.879Z'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', 'ISO8601'],
                        'source_timezone': 'Europe/Berlin',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_UNIX_with_millis_timestamp(self, normalizer):
        expected = {
            '@timestamp': '2022-01-14T12:40:49.843000+01:00',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1642160449843'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1642160449843'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['UNIX'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'Europe/Berlin'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_UNIX_with_seconds_timestamp(self, normalizer):
        expected = {
            '@timestamp': '2022-01-14T12:40:49+01:00',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1642160449'
                }
            }
        }

        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1642160449'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['UNIX'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'Europe/Berlin'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_non_matching_patterns(self, normalizer):
        event = {
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22 UTC'
                }
            }
        }

        expected = copy.deepcopy(event)

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['a%Y', 'a%Y %m', 'ISO8601'],
                        'source_timezone': 'UTC',
                        'destination_timezone': 'Europe/Berlin'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        with pytest.raises(NormalizerError):
            normalizer.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_collision(self, normalizer):
        expected = {
            '@timestamp': '1999-12-12T11:12:22Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        event = {
            '@timestamp': '2200-02-01T16:19:22Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'Europe/Berlin',
                        'destination_timezone': 'UTC'
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected

    def test_normalization_from_timestamp_with_collision_without_allow_override_fails(self, normalizer):
        event = {
            '@timestamp': '2200-02-01T16:19:22Z',
            'winlog': {
                'api': 'wineventlog',
                'event_id': 123456789,
                'event_data': {
                    'some_timestamp_utc': '1999 12 12 - 12:12:22'
                }
            }
        }

        expected = copy.deepcopy(event)

        rule = {
            'filter': 'winlog.event_id: 123456789',
            'normalize': {
                'winlog.event_data.some_timestamp_utc': {
                    'timestamp': {
                        'destination': '@timestamp',
                        'source_formats': ['%Y', '%Y %m %d - %H:%M:%S'],
                        'source_timezone': 'Europe/Berlin',
                        'destination_timezone': 'UTC',
                        'allow_override': False
                    }
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        with pytest.raises(ProcessingWarning,
                           match=r'The following fields already existed and were not '
                                 r'overwritten by the Normalizer: @timestamp\)'):
            normalizer.process(event)

        assert event == expected

    def test_normalization_with_replace_html_entity(self, normalizer):
        event = {
            'tags': ['testtag'],
            'message': 'replace=MAX&#43;&#8364;MORITZ&amp;dont_replace=FOO&#43;BAR&amp;id=5'
        }

        expected = {
            'tags': ['testtag'],
            'message': 'replace=MAX&#43;&#8364;MORITZ&amp;dont_replace=FOO&#43;BAR&amp;id=5',
            'test': {
                'id': '5',
                'dont_replace': 'FOO&#43;BAR',
                'replace': 'MAX&#43;&#8364;MORITZ',
                'replace_decodiert': 'MAX+€MORITZ'
            }
        }

        rule = {
            'filter': 'tags: testtag',
            'normalize': {
                'message': {
                    'grok': 'replace=%{DATA:[test][replace]}'
                            '&amp;dont_replace=%{DATA:[test][dont_replace]}&amp;id=%{INT:[test][id]}'
                }
            }
        }

        self._load_specific_rule(normalizer, rule)
        normalizer.process(event)

        assert event == expected


class TestNormalizerFactory:
    VALID_CONFIG = {
        'type': 'normalizer',
        'specific_rules': specific_rules_dir,
        'generic_rules': generic_rules_dir,
        'regex_mapping': cap_group_regex_mapping
    }

    def test_create(self):
        assert isinstance(NormalizerFactory.create('foo', self.VALID_CONFIG, logger), Normalizer)

    def test_check_configuration(self):
        NormalizerFactory._check_configuration(self.VALID_CONFIG)
        for i in range(len(self.VALID_CONFIG)):
            cfg = copy.deepcopy(self.VALID_CONFIG)
            cfg.pop(list(cfg)[i])
            with pytest.raises(ProcessorFactoryError):
                NormalizerFactory._check_configuration(cfg)
