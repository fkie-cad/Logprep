# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
from collections import OrderedDict
from copy import deepcopy

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.generic_resolver.processor import GenericResolver
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestGenericResolver(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_generic_resolver",
        "rules": ["tests/testdata/unit/generic_resolver/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    expected_metrics = [
        "logprep_generic_resolver_new_results",
        "logprep_generic_resolver_cached_results",
        "logprep_generic_resolver_num_cache_entries",
        "logprep_generic_resolver_cache_load",
    ]

    def test_resolve_generic_instantiates(self):
        rule = {"filter": "anything", "generic_resolver": {"field_mapping": {}}}
        self._load_rule(rule)
        assert isinstance(self.object, GenericResolver)

    def test_resolve_not_dotted_field_no_conflict_match(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_rule(rule)

        expected = {"to_resolve": "something HELLO1", "resolved": "Greeting"}

        document = {"to_resolve": "something HELLO1"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_with_dict_value(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": {"Greeting": "Hello"}},
            },
        }

        self._load_rule(rule)

        expected = {"to_resolve": "something HELLO1", "resolved": {"Greeting": "Hello"}}
        document = {"to_resolve": "something HELLO1"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_resolve_from_mapping_with_ignore_case(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
                "ignore_case": True,
            },
        }

        self._load_rule(rule)

        expected = {"to_resolve": "something HELLO1", "resolved": "Greeting"}
        document = {"to_resolve": "something HELLO1"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

        expected = {"to_resolve": "something hello1", "resolved": "Greeting"}
        document = {"to_resolve": "something hello1"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_resolve_not_dotted_field_no_conflict_and_to_list_entries_match(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting", ".*BYE\\d": "Farewell"},
            },
        }

        self._load_rule(rule)

        expected = {"to_resolve": "something HELLO1", "resolved": "Greeting"}

        document = {"to_resolve": "something HELLO1"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

        expected = {"to_resolve": "something BYE1", "resolved": "Farewell"}

        document = {"to_resolve": "something BYE1"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_resolve_not_dotted_field_no_conflict_no_match(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }

        self._load_rule(rule)

        expected = {"to_resolve": "something no"}
        document = {"to_resolve": "something no"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_match(self):
        rule = {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {"to": {"resolve": "something HELLO1"}, "resolved": "Greeting"}

        document = {"to": {"resolve": "something HELLO1"}}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_match_from_file(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_server_type"}

        document = {"to_resolve": "ab"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_from_file_with_ignore_case(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "ignore_case": True,
                "resolve_list": {"FOO": "BAR"},
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "ab", "resolved": "ab_server_type"}
        document = {"to_resolve": "ab"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

        expected = {"to_resolve": "AB", "resolved": "ab_server_type"}
        document = {"to_resolve": "AB"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_resolve_from_file_and_from_list(self):
        rule = {
            "filter": "to_resolve_1 AND to_resolve_2",
            "generic_resolver": {
                "field_mapping": {
                    "to_resolve_1": "resolved_1",
                    "to_resolve_2": "resolved_2",
                },
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"fg": "fg_server_type"},
            },
        }

        self._load_rule(rule)

        expected = {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_server_type",
            "resolved_2": "fg_server_type",
        }

        document = {"to_resolve_1": "ab", "to_resolve_2": "fg"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_no_match_from_file(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"FOO": "BAR"},
            },
        }
        self._load_rule(rule)

        expected = {
            "to_resolve": "not_in_list",
        }

        document = {"to_resolve": "not_in_list"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_match_from_file_and_list(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}

        document = {"to_resolve": "12ab34"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}

        document = {"to_resolve": "12ab34"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict_and_diff_inputs(
        self,
    ):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {
                    "to_resolve": "resolved",
                    "other_to_resolve": "resolved",
                },
                "resolve_from_file": {
                    "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        }
        self._load_rule(rule)

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_server_type", "de_server_type"],
        }

        document = {"to_resolve": "12ab34", "other_to_resolve": "00de11"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_no_conflict_no_match(self):
        rule = {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {"to": {"resolve": "something no"}}
        document = {"to": {"resolve": "something no"}}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_field_is_missing(self):
        rule = {
            "filter": "to.other_field",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {
            "to": {"other_field": "something no"},
            "tags": ["_generic_resolver_missing_field_warning"],
        }
        document = {"to": {"other_field": "something no"}}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_dest_field_no_conflict_match(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "something HELLO1", "re": {"solved": "Greeting"}}
        document = {"to_resolve": "something HELLO1"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_dest_field_no_conflict_no_match(self):
        rule = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {"to_resolve": "something no"}
        document = {"to_resolve": "something no"}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_src_and_dest_field_no_conflict_match(
        self,
    ):
        rule = {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)

        expected = {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}}
        document = {"to": {"resolve": "something HELLO1"}}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_dotted_src_and_dest_field_and_conflict_match(self, caplog):
        rule = {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        }
        self._load_rule(rule)
        document = {
            "to": {"resolve": "something HELLO1"},
            "re": {"solved": "I already exist!"},
        }
        expected = {
            "tags": ["_generic_resolver_failure"],
            "to": {"resolve": "something HELLO1"},
            "re": {"solved": "I already exist!"},
        }
        result = log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    def test_resolve_generic_and_multiple_match_first_only(self):
        rule = {
            "filter": "to.resolve",
            "generic_resolver": {
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

        self._load_rule(rule)
        expected = {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}}
        document = {"to": {"resolve": "something HELLO1"}}

        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_resolve_from_cache_with_large_enough_cache(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        rule_dict = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
            },
        }
        event = {"to_resolve": "foo"}
        self._load_rule(rule_dict)
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        event_bar = {"to_resolve": "bar"}
        log_event_bar = LogEvent(event_bar, original=b"")
        self.object.process(log_event_bar)

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 4

    def test_resolve_from_cache_with_cache_smaller_than_results(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 1
        self.object = Factory.create({"generic_resolver": config})

        rule_dict = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
            },
        }
        event = {"to_resolve": "foo"}
        self._load_rule(rule_dict)
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        event_bar = {"to_resolve": "bar"}
        log_event_bar = LogEvent(event_bar, original=b"")
        self.object.process(log_event_bar)

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 3

    def test_resolve_without_cache(self):
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 0
        self.object = Factory.create({"generic_resolver": config})

        rule_dict = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
            },
        }
        event = {"to_resolve": "foo"}
        self._load_rule(rule_dict)
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        event_bar = {"to_resolve": "bar"}
        log_event_bar = LogEvent(event_bar, original=b"")
        self.object.process(log_event_bar)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

    def test_resolve_from_cache_with_update_interval_2(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["cache_metrics_interval"] = 2
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        rule_dict = {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
            },
        }
        event = {"to_resolve": "foo"}
        other_event = {"to_resolve": "bar"}
        self._load_rule(rule_dict)
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        log_event_other = LogEvent(other_event, original=b"")
        self.object.process(log_event_other)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        log_event_other = LogEvent(other_event, original=b"")
        self.object.process(log_event_other)

        assert self.object.metrics.new_results == 3
        assert self.object.metrics.cached_results == 3
        assert self.object.metrics.num_cache_entries == 3
