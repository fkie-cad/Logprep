# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
from collections import OrderedDict
from logging import getLogger

import pytest

from tests.unit.processor.base import BaseProcessorTestCase

from logprep.processor.hyperscan_resolver.rule import (
    InvalidHyperscanResolverDefinition,
    HyperscanResolverRule,
)

pytest.importorskip("logprep.processor.hyperscan_resolver")

from logprep.processor.hyperscan_resolver.factory import HyperscanResolverFactory
from logprep.processor.hyperscan_resolver.processor import (
    HyperscanResolver,
    DuplicationError,
    HyperscanResolverError,
)

logger = getLogger()


class TestHyperscanResolverProcessor(BaseProcessorTestCase):

    factory = HyperscanResolverFactory

    CONFIG = {
        "type": "hyperscan_resolver",
        "specific_rules": ["tests/testdata/unit/hyperscan_resolver/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/hyperscan_resolver/rules/generic/"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def specific_rules_dirs(self):
        """Return the paths of the specific rules"""
        return self.CONFIG["specific_rules"]

    @property
    def generic_rules_dirs(self):
        """Return the paths of the generic rules"""
        return self.CONFIG["generic_rules"]

    def _load_specific_rule(self, rule):
        specific_rule = HyperscanResolverRule._create_from_dict(rule)
        specific_rule.file_name = "some_file_name_is_required_for_hyperscan"
        self.object._specific_tree.add_rule(specific_rule, self.logger)

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
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_server_type"}
        document = {"to_resolve": "ab"}

        self.object.process(document)

        assert document == expected

    def test_resolve_from_file_and_from_list(self):
        rule = {
            "filter": "to_resolve_1 AND to_resolve_2",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve_1": "resolved_1", "to_resolve_2": "resolved_2"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
                "resolve_list": {"fg": "fg_server_type"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_server_type",
            "resolved_2": "fg_server_type",
        }
        document = {"to_resolve_1": "ab", "to_resolve_2": "fg"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_no_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
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
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
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
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
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
                "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_server_type", "de_server_type"],
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
                "resolve_from_file": "foo",
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

    factory = HyperscanResolverFactory

    CONFIG = {
        "type": "hyperscan_resolver",
        "specific_rules": ["tests/testdata/unit/hyperscan_resolver/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/hyperscan_resolver/rules/generic/"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def specific_rules_dirs(self):
        """Return the paths of the specific rules"""
        return self.CONFIG["specific_rules"]

    @property
    def generic_rules_dirs(self):
        """Return the paths of the generic rules"""
        return self.CONFIG["generic_rules"]

    def _load_specific_rule(self, rule):
        specific_rule = HyperscanResolverRule._create_from_dict(rule)
        specific_rule.file_name = "some_file_name_is_required_for_hyperscan"
        self.object._specific_tree.add_rule(specific_rule, self.logger)

    def test_resolve_dotted_no_conflict_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_server_type"}
        document = {"to_resolve": "ab"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_from_file_and_unbalanced_parenthesis(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)c)\d*",
                },
            },
        }

        with pytest.raises(Exception, match="unbalanced parenthesis"):
            self._load_specific_rule(rule)

    def test_resolve_dotted_no_conflict_from_file_and_escaped_parenthesis(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+\)c)\d*",
                },
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "ab)c", "resolved": "ab)c_server_type"}
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
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+\\\)c)\d*",
                },
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": r"ab\)c", "resolved": r"ab\)c_server_type"}
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
                    "/resolve_mapping_without_patterns.yml",
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
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"fg": "fg_server_type"},
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_server_type",
            "resolved_2": "fg_server_type",
        }
        document = {"to_resolve_1": "ab", "to_resolve_2": "fg"}

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_no_conflict_no_from_file(self):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
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

    def test_resolve_dotted_no_conflict_from_file_and_list(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
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
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>(([a-z])+)())\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
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
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "gh", "resolved": ["gh_server_type"]}
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
                    "/resolve_mapping_without_patterns.yml",
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

    def test_resolve_dotted_no_conflict_from_file_and_list_has_conflict(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "hyperscan_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
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
                "resolve_from_file": {
                    "path": "tests/testdata/unit/hyperscan_resolver"
                    "/resolve_mapping_without_patterns.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "append_to_list": True,
            },
        }

        self._load_specific_rule(rule)

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_server_type", "de_server_type"],
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
                    "path": "tests/testdata/unit/hyperscan_resolver/resolve_mapping.yml",
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
                "resolve_from_file": {"path": "foo", "pattern": "bar"},
            },
        }

        with pytest.raises(
            InvalidHyperscanResolverDefinition,
            match=r"The following HyperscanResolver definition is invalid: Additions file '{"
            r"'path': 'foo', 'pattern': 'bar'}' not found!",
        ):
            self._load_specific_rule(rule)
