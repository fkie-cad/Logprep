# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
from collections import OrderedDict
from copy import deepcopy

import pytest

pytest.importorskip("hyperscan")

from tests.unit.processor.base import BaseProcessorTestCase

from logprep.processor.hyperscan_resolver.rule import (
    InvalidHyperscanResolverDefinition,
)

pytest.importorskip("logprep.processor.hyperscan_resolver")

from logprep.processor.hyperscan_resolver.processor import (
    HyperscanResolver,
    DuplicationError,
    HyperscanResolverError,
)


class TestHyperscanResolverProcessor(BaseProcessorTestCase):

    CONFIG = {
        "type": "hyperscan_resolver",
        "specific_rules": ["tests/testdata/unit/hyperscan_resolver/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/hyperscan_resolver/rules/generic/"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "hyperscan_db_path": "/tmp",
    }

    def test_resolve_instantiates(self):
        rule = {"filter": "anything", "hyperscan_resolver": {"field_mapping": {}}}

        self._load_specific_rule(rule)

        assert isinstance(self.object, HyperscanResolver)

    def test_resolve_not_dotted_field_no_conflict_match(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "something HELLO1", "resolved": "Greeting"}
        document = {"to_resolve": "something HELLO1"}

        self.object.process(document)

        assert document == expected

    def test_resolve_not_dotted_field_no_conflict_and_to_list_entries_match(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting", ".*BYE\\d": "Farewell"},
            },
        }

        self._load_specific_rule(rule)
        expected = {"to_resolve": "something HELLO1", "resolved": "Greeting"}
        document = {"to_resolve": "something HELLO1"}

        self.object.process(document)
        assert document == expected

        expected = {"to_resolve": "something BYE1", "resolved": "Farewell"}
        document = {"to_resolve": "something BYE1"}

        self.object.process(document)
        assert document == expected

    def test_resolve_not_dotted_field_no_conflict_no_match(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "something no"}
        document = {"to_resolve": "something no"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_match(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to": {"resolve": "something HELLO1"}, "resolved": "Greeting"}
        document = {"to": {"resolve": "something HELLO1"}}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_resolved"}
        document = {"to_resolve": "ab"}

        self.object.process(document)

        assert document == expected

    def test_resolve_from_file_and_from_list(self):
        rule = {
            "filter": "to_resolve_1 AND to_resolve_2",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve_1": "resolved_1", "to_resolve_2": "resolved_2"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "resolve_list": {"fg": "fg_resolved"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_resolved",
            "resolved_2": "fg_resolved",
        }
        document = {"to_resolve_1": "ab", "to_resolve_2": "fg"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_no_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "not_in_list",
        }
        document = {"to_resolve": "not_in_list"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_list(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_resolved"]}
        document = {"to_resolve": "12ab34"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_list_has_conflict(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_resolved"]}
        document = {"to_resolve": "12ab34"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_list_has_conflict_and_diff_inputs(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved", "other_to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                "resolve_mapping_no_regex.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_resolved", "de_resolved"],
        }
        document = {"to_resolve": "12ab34", "other_to_resolve": "00de11"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    def test_resolve_from_file_and_file_does_not_exist(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_from_file": "i/do/not/exist",
            },
        }

        with pytest.raises(InvalidHyperscanResolverDefinition):
            self._load_specific_rule(rule)

    def test_resolve_dotted_no_conflict_no_match(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to": {"resolve": "something no"}}
        document = {"to": {"resolve": "something no"}}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_dest_field_no_conflict_match(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "something HELLO1", "re": {"solved": "Greeting"}}
        document = {"to_resolve": "something HELLO1"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_dest_field_no_conflict_no_match(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "something no"}
        document = {"to_resolve": "something no"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_and_dest_field_no_conflict_match(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}}
        document = {"to": {"resolve": "something HELLO1"}}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_and_dest_field_with_conflict_match(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_specific_rule(rule)

        document = {"to": {"resolve": "something HELLO1"}, "re": {"solved": "I already exist!"}}

        with pytest.raises(DuplicationError):
            self.object.process(document)

    def test_resolve_with_multiple_match_first_only(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": OrderedDict(
                    {
                        ".*HELLO\\d": "Greeting",
                        ".*HELL.\\d": "Greeting2",
                        ".*HEL..\\d": "Greeting3",
                    }
                ),
            },
        }

        self._load_specific_rule(rule)

        expected = {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}}
        document = {"to": {"resolve": "something HELLO1"}}

        self.object.process(document)

        assert document == expected


class TestHyperscanResolverProcessorWithPatterns(BaseProcessorTestCase):

    CONFIG = deepcopy(TestHyperscanResolverProcessor.CONFIG)

    def test_resolve_no_conflict_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_resolved"}
        document = {"to_resolve": "ab"}

        self.object.process(document)

        assert document == expected

    def test_resolve_no_conflict_from_file_and_escaped_parenthesis(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_with_parenthesis.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+\)c)\d*",
                },
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab)c", "resolved": "ab)c_resolved"}
        document = {"to_resolve": "ab)c"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_escaped_parenthesis_and_backslash(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_with_parenthesis.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+\\\)c)\d*",
                },
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": r"ab\)c", "resolved": r"ab\)c_resolved"}
        document = {"to_resolve": r"ab\)c"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_escaped_to_unbalanced_parenthesis(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_with_parenthesis.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+\\\\)c)\d*",
                },
            },
        }

        with pytest.raises(Exception, match="unbalanced parenthesis"):
            self._load_specific_rule(rule)

    def test_resolve_from_file_and_from_list(self):
        rule = {
            "filter": "to_resolve_1 AND to_resolve_2",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve_1": "resolved_1", "to_resolve_2": "resolved_2"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"fg": "fg_resolved"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_resolved",
            "resolved_2": "fg_resolved",
        }
        document = {"to_resolve_1": "ab", "to_resolve_2": "fg"}

        self.object.process(document)

        assert document == expected

    def test_resolve_no_conflict_no_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "not_in_list",
        }
        document = {"to_resolve": "not_in_list"}

        self.object.process(document)

        assert document == expected

    def test_resolve_no_conflict_from_file_and_list(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_resolved"]}
        document = {"to_resolve": "12ab34"}

        self.object.process(document)

        assert document == expected

    def test_resolve_with_parenthesis_in_mapping(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_with_parenthesis.yml",
                    "pattern": r"\d*(?P<mapping>(([a-z])+)())\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_resolved"]}
        document = {"to_resolve": "12ab34"}

        self.object.process(document)

        assert document == expected

    def test_resolve_with_partially_matching_mapping(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "gh", "resolved": ["gh_resolved"]}
        document = {"to_resolve": "gh"}

        self.object.process(document)

        assert document == expected

    def test_resolve_no_matching_pattern(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[123]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        document = {"to_resolve": "12ab34"}

        with pytest.raises(
            HyperscanResolverError, match=r"No patter to compile for hyperscan database!"
        ):
            self.object.process(document)

    def test_resolve_no_conflict_from_file_and_list_has_conflict(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_resolved"]}
        document = {"to_resolve": "12ab34"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    def test_resolve_no_conflict_from_file_and_list_has_conflict_and_diff_inputs(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved", "other_to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_no_regex.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_resolved", "de_resolved"],
        }
        document = {"to_resolve": "12ab34", "other_to_resolve": "00de11"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_group_mapping_does_not_exist(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver/resolve_mapping_regex.yml",
                    "pattern": r"\d*(?P<foobar>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        document = {"to_resolve": "ab"}

        self.object.process(document)

    def test_resolve_from_file_and_file_does_not_exist(self):
        rule = {
            "filter": "to.resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_from_file": {"path": "i/do/not/exist", "pattern": "bar"},
            },
        }

        with pytest.raises(
            InvalidHyperscanResolverDefinition,
            match=r"The following HyperscanResolver definition is invalid: Additions file '{"
            r"'path': 'i/do/not/exist', 'pattern': 'bar'}' not found!",
        ):
            self._load_specific_rule(rule)
