from logging import getLogger

import pytest

from logprep.processor.list_comparison.processor import DuplicationError

pytest.importorskip('logprep.processor.list_comparison')

from logprep.processor.list_comparison.factory import ListComparisonFactory

logger = getLogger()
rules_dir = 'tests/testdata/unit/list_comparison/rules'


@pytest.fixture()
def list_comparison():
    config = {
        'type': 'list_comparison',
        'rules': [rules_dir],
        'timeout': 0.25, 'max_cached_domains': 1000000,
        'max_caching_days': 1, 'hash_salt': 'a_secret_tasty_ingredient',
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }

    list_comparison = ListComparisonFactory.create('test-list-comparison', config, logger)
    return list_comparison


class TestListComparison:
    def test_element_in_list(self, list_comparison):
        # Tests if user Franz is in user list
        assert list_comparison.events_processed_count() == 0
        document = {'user': 'Franz'}

        list_comparison.process(document)

        assert document.get('user_results', {}).get('in_list') is not []
        assert document.get('user_results', {}).get('not_in_list') is None

    def test_element_not_in_list(self, list_comparison):
        # Test if user Charlotte is not in user list
        assert list_comparison.events_processed_count() == 0
        document = {'user': 'Charlotte'}

        list_comparison.process(document)

        assert document.get('user_results', {}).get('not_in_list') is not []
        assert document.get('user_results', {}).get('in_list') is None

    def test_element_in_two_lists(self, list_comparison):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        assert list_comparison.events_processed_count() == 0
        document = {'user': 'Mark', 'system': "Franz"}

        list_comparison.process(document)

        assert len(document.get('user_results', {}).get('not_in_list')) is 1
        assert document.get('user_results', {}).get('in_list') is None
        assert len(document.get('user_and_system_results', {}).get('in_list')) is 2
        assert document.get('user_and_system_results', {}).get('not_in_list') is None

    def test_element_not_in_two_lists(self, list_comparison):
        # Tests if the system Gamma does not appear in two lists, and username Mark is also not in list
        assert list_comparison.events_processed_count() == 0
        document = {'user': 'Mark', 'system': "Gamma"}

        list_comparison.process(document)

        assert len(document.get('user_and_system_results', {}).get('not_in_list')) is 2
        assert document.get('user_and_system_results', {}).get('in_list') is None
        assert len(document.get('user_results', {}).get('not_in_list')) is 1
        assert document.get('user_results', {}).get('in_list') is None

    def test_two_lists_with_one_matched(self, list_comparison):
        assert list_comparison.events_processed_count() == 0
        document = {'system': 'Alpha', 'user': 'Charlotte'}

        list_comparison.process(document)

        assert document.get('user_results', {}).get('not_in_list') is not []
        assert document.get('user_results', {}).get('in_list') is None
        assert document.get('user_and_system_results', {}).get('not_in_list') is None
        assert document.get('user_and_system_results', {}).get('in_list') is not []

    def test_dotted_output_field(self, list_comparison):
        # tests if outputting list_comparison results to dotted fields works
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz'}

        list_comparison.process(document)

        assert document.get('dotted', {}).get('user_results', {}).get('not_in_list') is None
        assert document.get('dotted', {}).get('user_results', {}).get('in_list') is not []

    def test_deep_dotted_output_field(self, list_comparison):
        # tests if outputting list_comparison results to dotted fields works
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz'}

        list_comparison.process(document)

        assert document.get('more', {}).get('than', {}).get('dotted', {}).get('user_results', {}).get('not_in_list') is None
        assert document.get('more', {}).get('than', {}).get('dotted', {}).get('user_results', {}).get('not_in_list') is not []

    def test_extend_dotted_output_field(self, list_comparison):
        # tests if list_comparison properly extends lists already present in output fields.
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz',
                    'dotted': {'user_results': {'in_list': ['already_present']}}}

        list_comparison.process(document)

        assert document.get('dotted', {}).get('user_results', {}).get('not_in_list') is None
        assert len(document.get('dotted', {}).get('user_results', {}).get('in_list')) == 2

    def test_dotted_parent_field_exists_but_subfield_doesnt(self, list_comparison):
        # tests if list_comparison properly extends lists already present in output fields.
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz',
                    'dotted': {'preexistent_output_field': {'in_list': ['already_present']}}}

        list_comparison.process(document)

        assert document.get('dotted', {}).get('user_results', {}).get('not_in_list') is None
        assert len(document.get('dotted', {}).get('user_results', {}).get('in_list')) == 1
        assert len(document.get('dotted', {}).get('preexistent_output_field', {}).get('in_list')) == 1

    def test_dotted_wrong_type(self, list_comparison):
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz',
                    'dotted': "dotted_Franz"}

        with pytest.raises(DuplicationError):
            list_comparison.process(document)

    def test_intermediate_output_field_is_wrong_type(self, list_comparison):
        assert list_comparison.events_processed_count() == 0
        document = {'dot_channel': 'test', 'user': 'Franz',
                    'dotted': {'user_results': ['do_not_look_here']}}

        with pytest.raises(DuplicationError):
            list_comparison.process(document)

    def test_check_in_dotted_subfield(self, list_comparison):
        assert list_comparison.events_processed_count() == 0
        document = {'channel': {'type': 'fast'}}

        list_comparison.process(document)

        assert len(document.get('channel_results', {}).get('not_in_list')) is 2
        assert document.get('channel_results', {}).get('in_list') is None

    def test_ignore_comment_in_list(self, list_comparison):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        assert list_comparison.events_processed_count() == 0
        document = {'user': '# This is a doc string for testing'}

        list_comparison.process(document)

        assert len(document.get('user_results', {}).get('not_in_list')) is 1
        assert document.get('user_results', {}).get('in_list') is None
