import pytest
pytest.importorskip('logprep.processor.dropper')

import copy
from logging import getLogger

from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.dropper.factory import Dropper, DropperFactory
from logprep.processor.processor_factory_error import ProcessorFactoryError
from logprep.processor.dropper.rule import DropperRule
from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning

logger = getLogger()
rules_dir = ['tests/testdata/unit/dropper/rules/']


@pytest.fixture()
def dropper():
    dropper = Dropper('Test Dropper Name', None, logger)
    dropper.add_rules_from_directory(rules_dir)
    return dropper


class TestDropper:
    @staticmethod
    def _load_rule(dropper, rule):
        rule = DropperRule._create_from_dict(rule)
        dropper._tree.add_rule(rule)

    def _load_single_rule(self, dropper, rule):
        dropper._tree = RuleTree(config_path=None)
        self._load_rule(dropper, rule)

    def test_is_a_processor_implementation(self, dropper):
        assert isinstance(dropper, RuleBasedProcessor)

    def test_describe(self, dropper):
        assert dropper.describe() == 'Dropper (Test Dropper Name)'

    def test_events_processed_count(self, dropper):
        assert dropper.events_processed_count() == 0
        document = {'foo': 'bar'}
        for i in range(1, 11):
            try:
                dropper.process(document)
            except ProcessingWarning:
                pass
            assert dropper.events_processed_count() == i

    def test_field_exists(self, dropper):
        dropper._event = {
            'a': {
                'b': {
                    'c': 'foo'}}}
        assert dropper._field_exists('a')
        assert dropper._field_exists('a.b')
        assert dropper._field_exists('a.b.c')
        assert not dropper._field_exists('foo')
        assert not dropper._field_exists('b')
        assert not dropper._field_exists('b.c')

    def test_not_nested_field_gets_dropped_with_rule_loaded_from_file(self, dropper):
        expected = {}
        document = {
            'drop_me': 'something'
        }
        dropper.process(document)

        assert document == expected

    def test_nested_field_gets_dropped(self, dropper):
        rule = {
            'filter': 'drop.me',
            'drop':  ['drop.me']
        }
        expected = {}
        document = {'drop': {'me': 'something'}}
        self._load_single_rule(dropper, rule)
        dropper.process(document)

        assert document == expected

    def test_nested_field_with_neighbours_gets_dropped(self, dropper):
        rule = {
            'filter': 'keep_me.drop_me',
            'drop':  ['keep_me.drop_me']
        }
        expected = {
            'keep_me': {
                'keep_me_too': 'something'
            }
        }
        document = {
            'keep_me': {
                'drop_me': 'something',
                'keep_me_too': 'something'
            }
        }
        self._load_single_rule(dropper, rule)
        dropper.process(document)

        assert document == expected

    def test_deep_nested_field_gets_dropped(self, dropper):
        rule = {
                  'filter': 'keep_me.drop.me',
                  'drop':  ['keep_me.drop.me'],
                  'drop_full': False
        }
        expected = {'keep_me': {'drop': {}}}
        document = {'keep_me': {'drop': {'me': 'something'}}}
        self._load_single_rule(dropper, rule)
        dropper.process(document)

        assert document == expected

    def test_deep_nested_field_gets_dropped_fully(self, dropper):
        rule = {
            'filter': 'please.drop.me.fully',
            'drop':  ['please.drop.me.fully']
        }
        expected = {}
        document = {'please': {'drop': {'me': {'fully': 'something'}}}}
        self._load_single_rule(dropper, rule)
        dropper.process(document)

        assert document == expected

    def test_deep_nested_field_with_neighbours_gets_dropped(self, dropper):
        rule = {
                  'filter': 'keep_me.drop.me',
                  'drop':  ['keep_me.drop.me'],
                  'drop_full': False
        }
        expected = {
            'keep_me': {
                'drop': {},
                'keep_me_too': 'something'
            }
        }
        document = {
            'keep_me': {
                'drop': {'me': 'something'},
                'keep_me_too': 'something'
            }
        }
        self._load_single_rule(dropper, rule)
        dropper.process(document)

        assert document == expected


class TestDropperFactory:
    VALID_CONFIG = {
        'type': 'dropper',
        'rules': rules_dir
    }

    def test_create(self):
        assert isinstance(DropperFactory.create('foo', self.VALID_CONFIG, logger), Dropper)

    def test_check_configuration(self):
        DropperFactory._check_configuration(self.VALID_CONFIG)
        for i in range(len(self.VALID_CONFIG)):
            cfg = copy.deepcopy(self.VALID_CONFIG)
            cfg.pop(list(cfg)[i])
            with pytest.raises(ProcessorFactoryError):
                DropperFactory._check_configuration(cfg)
