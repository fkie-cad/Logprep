from logging import getLogger

import pytest

pytest.importorskip('logprep.processor.generic_adder')

from logprep.processor.base.exceptions import InvalidRuleFileError

from logprep.processor.generic_adder.factory import GenericAdderFactory
from logprep.processor.generic_adder.processor import DuplicationError


logger = getLogger()
rules_dir = 'tests/testdata/unit/generic_adder/rules'
rules_dir_missing = 'tests/testdata/unit/generic_adder/rules_missing'
rules_dir_invalid = 'tests/testdata/unit/generic_adder/rules_invalid'
rules_dir_first_existing = 'tests/testdata/unit/generic_adder/rules_first_existing'


@pytest.fixture()
def generic_adder():
    config = {
        'type': 'generic_adder',
        'rules': [rules_dir],
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }

    generic_adder = GenericAdderFactory.create('test-generic-adder', config, logger)
    return generic_adder


class TestGenericAdder:
    def test_add_generic_fields(self, generic_adder):
        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file(self, generic_adder):
        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_list_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_list_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_one_element(self, generic_adder):
        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_lists_one_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_lists_one_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_two_elements(self, generic_adder):
        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_lists_two_generic_test': 'Test', 'event_id': 123,
            'added_from_other_file': 'some field from another file',
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_lists_two_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing(self):
        config = {
            'type': 'generic_adder',
            'rules': [rules_dir_first_existing],
            'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
        }

        generic_adder = GenericAdderFactory.create('test-generic-adder', config, logger)

        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_first_existing_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_first_existing_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing_with_missing(self):
        config = {
            'type': 'generic_adder',
            'rules': [rules_dir_first_existing],
            'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
        }

        generic_adder = GenericAdderFactory.create('test-generic-adder', config, logger)

        assert generic_adder.events_processed_count() == 0
        expected = {
            'add_first_existing_with_missing_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_first_existing_with_missing_generic_test': 'Test', 'event_id': 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidRuleFileError, match=r'files do not exist'):
            config = {
                'type': 'generic_adder',
                'rules': [rules_dir_missing],
                'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
            }

            GenericAdderFactory.create('test-generic-adder', config, logger)

    def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(InvalidRuleFileError, match=r'must be a dictionary with string values'):
            config = {
                'type': 'generic_adder',
                'rules': [rules_dir_invalid],
                'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
            }

            GenericAdderFactory.create('test-generic-adder', config, logger)

    def test_add_generic_fields_to_co_existing_field(self, generic_adder):
        expected = {
            'add_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some value',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'},
                       'i_exist': 'already'}
        }
        document = {'add_generic_test': 'Test', 'event_id': 123, 'dotted': {'i_exist': 'already'}}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_to_existing_value(self, generic_adder):
        expected = {
            'add_generic_test': 'Test', 'event_id': 123,
            'some_added_field': 'some_non_dict',
            'another_added_field': 'another_value',
            'dotted': {'added': {'field': 'yet_another_value'}}
        }
        document = {'add_generic_test': 'Test', 'event_id': 123, 'some_added_field': 'some_non_dict'}

        with pytest.raises(DuplicationError):
            generic_adder.process(document)

        assert document == expected
