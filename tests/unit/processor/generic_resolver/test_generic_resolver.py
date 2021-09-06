from logging import getLogger
import tempfile
from os import path
from shutil import rmtree
from pathlib import Path
from json import dumps
from collections import OrderedDict

import pytest

pytest.importorskip('logprep.processor.generic_resolver')

from logprep.processor.generic_resolver.factory import GenericResolverFactory
from logprep.processor.generic_resolver.processor import GenericResolver, DuplicationError, GenericResolverError

logger = getLogger()
rules_dir = 'tests/testdata/generic_resolver/rules'


@pytest.fixture()
def generic_resolver_config():
    config = {
        'type': 'generic_resolver',
        'rules': [rules_dir],
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }
    return config


@pytest.fixture()
def temp_rule_dir():
    def remove_dir_if_exists(test_output_path):
        try:
            rmtree(test_output_path)
        except FileNotFoundError:
            pass

    temp_dir = tempfile.gettempdir()
    temp_rule_dir = path.join(temp_dir, 'test_preprocessor_rules')
    remove_dir_if_exists(temp_rule_dir)
    Path(temp_rule_dir).mkdir(parents=True, exist_ok=True)
    yield temp_rule_dir
    remove_dir_if_exists(temp_rule_dir)


class TestGenericResolver:
    def test_resolve_generic_instantiates(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            "filter": "anything",
            "generic_resolver": {
                "field_mapping": {}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)
        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        assert isinstance(generic_resolver, GenericResolver)

    def test_resolve_generic_existing_not_dotted_field_without_conflict_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_list': {'.*HELLO\\d': 'Greeting'}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': 'something HELLO1',
            'resolved': 'Greeting'
        }

        document = {'to_resolve': 'something HELLO1'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_not_dotted_field_without_conflict_and_to_list_entries_match(self, temp_rule_dir,
                                                                                                  generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting',
                    '.*BYE\\d': 'Farewell'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': 'something HELLO1',
            'resolved': 'Greeting'
        }

        document = {'to_resolve': 'something HELLO1'}
        generic_resolver.process(document)
        assert document == expected

        expected = {
            'to_resolve': 'something BYE1',
            'resolved': 'Farewell'
        }

        document = {'to_resolve': 'something BYE1'}
        generic_resolver.process(document)
        assert document == expected

    def test_resolve_generic_existing_not_dotted_field_without_conflict_no_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to_resolve': 'something no'}
        document = {'to_resolve': 'something no'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 'resolved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to': {'resolve': 'something HELLO1'},
            'resolved': 'Greeting'
        }

        document = {'to': {'resolve': 'something HELLO1'}}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match_from_file(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                'resolve_list': {'FOO': 'BAR'}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': 'ab',
            'resolved': 'ab_server_type'
        }

        document = {'to_resolve': 'ab'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_from_file_and_from_list(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve_1 AND to_resolve_2',
                'generic_resolver': {
                    'field_mapping': {'to_resolve_1': 'resolved_1', 'to_resolve_2': 'resolved_2'},
                    'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                    'resolve_list': {'fg': 'fg_server_type'}
                }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve_1': 'ab',
            'to_resolve_2': 'fg',
            'resolved_1': 'ab_server_type',
            'resolved_2': 'fg_server_type'
        }

        document = {'to_resolve_1': 'ab', 'to_resolve_2': 'fg'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_no_match_from_fileF(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                'resolve_list': {'FOO': 'BAR'}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': 'not_in_list',
        }

        document = {'to_resolve': 'not_in_list'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match_from_file_with_list(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                'append_to_list': True
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': '12ab34',
            'resolved': ['ab_server_type']
        }

        document = {
            'to_resolve': '12ab34'
        }

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match_from_file_with_list_has_conflict(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                'append_to_list': True
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': '12ab34',
            'resolved': ['ab_server_type']
        }

        document = {
            'to_resolve': '12ab34'
        }

        generic_resolver.process(document)
        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match_from_file_with_list_has_conflict_and_different_inputs(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved', 'other_to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<mapping>[a-z]+)\d*'},
                'append_to_list': True
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {
            'to_resolve': '12ab34',
            'other_to_resolve': '00de11',
            'resolved': ['ab_server_type', 'de_server_type']
        }

        document = {
            'to_resolve': '12ab34',
            'other_to_resolve': '00de11'
        }

        generic_resolver.process(document)
        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_field_without_conflict_match_from_file_group_mapping_does_not_exist(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 'resolved'},
                'resolve_from_file': {'path': 'tests/testdata/unit/generic_resolver/resolve_mapping.yml', 'pattern': r'\d*(?P<foobar>[a-z]+)\d*'},
                'resolve_list': {'FOO': 'BAR'}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        document = {'to_resolve': 'ab'}

        with pytest.raises(GenericResolverError, match=r'GenericResolver \(test-generic-resolver\)\: Mapping group is missing in mapping file pattern!'):
            generic_resolver.process(document)

    def test_resolve_generic_match_from_file_and_file_does_not_exist(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 'resolved'},
                'resolve_from_file': {'path': 'foo', 'pattern': 'bar'}
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        document = {'to': {'resolve': 'something HELLO1'}}

        with pytest.raises(GenericResolverError, match=r'GenericResolver \(test-generic-resolver\)\: Additions file \'foo\' not found!'):
            generic_resolver.process(document)

    def test_resolve_generic_existing_dotted_src_field_without_conflict_no_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 'resolved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to': {'resolve': 'something no'}}
        document = {'to': {'resolve': 'something no'}}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_dest_field_without_conflict_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 're.solved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to_resolve': 'something HELLO1', 're': {'solved': 'Greeting'}}
        document = {'to_resolve': 'something HELLO1'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_dest_field_without_conflict_no_match(self, temp_rule_dir, generic_resolver_config):
        rule = [{
            'filter': 'to_resolve',
            'generic_resolver': {
                'field_mapping': {'to_resolve': 're.solved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to_resolve': 'something no'}
        document = {'to_resolve': 'something no'}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_and_dest_field_without_conflict_match(self, temp_rule_dir,
                                                                                       generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 're.solved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to': {'resolve': 'something HELLO1'}, 're': {'solved': 'Greeting'}}
        document = {'to': {'resolve': 'something HELLO1'}}

        generic_resolver.process(document)

        assert document == expected

    def test_resolve_generic_existing_dotted_src_and_dest_field_with_conflict_match(self, temp_rule_dir,
                                                                                    generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 're.solved'},
                'resolve_list': {
                    '.*HELLO\\d': 'Greeting'
                }
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        document = {'to': {'resolve': 'something HELLO1'}, 're': {'solved': 'I already exist!'}}

        with pytest.raises(DuplicationError):
            generic_resolver.process(document)

    def test_resolve_generic_with_multiple_match_first_only(self, temp_rule_dir,
                                                                                    generic_resolver_config):
        rule = [{
            'filter': 'to.resolve',
            'generic_resolver': {
                'field_mapping': {'to.resolve': 're.solved'},
                'resolve_list': OrderedDict({
                    '.*HELLO\\d': 'Greeting',
                    '.*HELL.\\d': 'Greeting2',
                    '.*HEL..\\d': 'Greeting3'
                })
            }
        }]

        self.setup_multi_rule(generic_resolver_config, rule, temp_rule_dir)

        generic_resolver = GenericResolverFactory.create('test-generic-resolver', generic_resolver_config, logger)

        expected = {'to': {'resolve': 'something HELLO1'}, 're': {'solved': 'Greeting'}}
        document = {'to': {'resolve': 'something HELLO1'}}

        generic_resolver.process(document)

        assert document == expected

    @staticmethod
    def setup_multi_rule(generic_resolver_config, rule, temp_rule_dir):
        with open(path.join(temp_rule_dir, 'test_rule.json'), 'w') as test_rule:
            test_rule.writelines(dumps(rule))
        generic_resolver_config['rules'] = [temp_rule_dir]
