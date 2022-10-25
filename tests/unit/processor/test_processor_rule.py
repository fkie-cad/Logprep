# pylint: disable=missing-docstring
# pylint: disable=protected-access
from unittest import mock

import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError

from logprep.processor.base.rule import Rule


class TestRule:
    @pytest.mark.parametrize(
        "file_data, raises",
        [
            (
                """
                filter: test_filter
                rule:
                    regex_fields: []
                description: this is a test rule
                """,
                None,
            ),
            (
                """
                [
                    {
                        "filter": "test_filter",
                        "rule": {}
                    }
                ]
                """,
                None,
            ),
            (
                """
                """,
                (InvalidRuleDefinitionError, "no rules in file"),
            ),
        ],
    )
    def test_create_rules_from_file(self, file_data, raises):
        mock_open = mock.mock_open(read_data=file_data)
        with mock.patch("builtins.open", mock_open):
            if raises:
                error, message = raises
                with pytest.raises(error, match=message):
                    rules = Rule.create_rules_from_file("mock_path.json")
            else:
                rules = Rule.create_rules_from_file("mock_path.json")
                assert isinstance(rules, list)
                assert isinstance(rules[0], Rule)
                rule = rules[0]
                assert "test_filter" in rule.filter_str
