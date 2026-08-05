# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=too-many-lines,too-many-arguments,too-many-positional-arguments
import json
from copy import deepcopy
from pathlib import Path

import pytest
import responses

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.generic_resolver.processor import GenericResolver
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter
from tests.conftest import field_value_test_cases, mock_env, normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

CONTENT_FIELD_URL = "http://localhost/resolve-mapping"


example_test_cases = [
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to_resolve": "something HELLO1"},
        {"to_resolve": "something HELLO1", "resolved": "Greeting"},
        id="resolve_list matches a regex pattern",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": {"Greeting": "Hello"}},
            },
        },
        {"to_resolve": "something HELLO1"},
        {"to_resolve": "something HELLO1", "resolved": {"Greeting": "Hello"}},
        id="resolve_list can resolve to a mapping value",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to_resolve": "something without a match"},
        {"to_resolve": "something without a match"},
        id="no match leaves the event unchanged",
    ),
    pytest.param(
        {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to": {"resolve": "something HELLO1"}},
        {"to": {"resolve": "something HELLO1"}, "resolved": "Greeting"},
        id="resolve a dotted source field",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
            },
        },
        {"to_resolve": "ab"},
        {"to_resolve": "ab", "resolved": "ab_server_type"},
        {
            "resolve_mapping.yml": {
                "body": {"ab": "ab_server_type", "de": "de_server_type"},
            }
        },
        id="resolve from a file",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": CONTENT_FIELD_URL,
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {
            CONTENT_FIELD_URL: {
                "body": {"content": {"ab": "ab_server_type", "de": "de_server_type"}},
            }
        },
        id="content_field selects the nested resolve mapping",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "to.other_field",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to": {"other_field": "something without the source field"}},
        {
            "to": {"other_field": "something without the source field"},
            "tags": ["_generic_resolver_missing_field_warning"],
        },
        id="missing source field adds a warning tag",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-zA-Z]+)\d*",
                },
                "ignore_case": True,
            },
        },
        {"to_resolve": "Ab"},
        {"to_resolve": "Ab", "resolved": "ab_server_type"},
        {
            "resolve_mapping.yml": {
                "body": {"ab": "ab_server_type", "de": "de_server_type"},
            }
        },
        id="resolve from a file, case-insensitive",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": CONTENT_FIELD_URL,
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {CONTENT_FIELD_URL: {"body": {"ab": "ab_server_type"}}},
        id="empty content_field reads the resolve mapping from the root",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to_resolve": "something HELLO1"},
        {"to_resolve": "something HELLO1", "re": {"solved": "Greeting"}},
        id="resolve into a dotted target field",
    ),
    pytest.param(
        {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to": {"resolve": "something HELLO1"}},
        {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}},
        id="resolve from a dotted source into a dotted target field",
    ),
    pytest.param(
        {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "re.solved"},
                "resolve_list": {
                    ".*HELLO\\d": "Greeting",
                    ".*HELL.\\d": "Greeting2",
                    ".*HEL..\\d": "Greeting3",
                },
            },
        },
        {"to": {"resolve": "something HELLO1"}},
        {"to": {"resolve": "something HELLO1"}, "re": {"solved": "Greeting"}},
        id="only the first matching pattern is applied",
    ),
    pytest.param(
        {
            "filter": "*",
            "generic_resolver": {
                "field_mapping": {"event.code": "event_description"},
                "resolve_list": {
                    "4624": "An account was successfully logged on.",
                    "4625": "An account failed to log on.",
                    "4634": "An account was logged off.",
                },
            },
        },
        {"event": {"code": 4625}},
        {"event": {"code": 4625}, "event_description": "An account failed to log on."},
        id="resolve a numeric source value",
    ),
    pytest.param(
        {
            "filter": "*",
            "generic_resolver": {
                "field_mapping": {"event.code": "event_description"},
                "resolve_list": {"4624": "An account was successfully logged on."},
            },
        },
        {"event": {"code": None}},
        {"event": {"code": None}, "tags": ["_generic_resolver_missing_field_warning"]},
        id="a null source value adds a warning tag",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
            },
        },
        {"to_resolve": "not_in_list"},
        {"to_resolve": "not_in_list"},
        {"resolve_mapping.yml": {"body": {"ab": "ab_server_type", "de": "de_server_type"}}},
        id="no match when resolving from a file",
    ),
    pytest.param(
        {
            "filter": "foo.bar",
            "generic_resolver": {
                "field_mapping": {"foo.bar": "foo"},
                "resolve_from_file": {
                    "path": "resolve_mapping_dict.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        },
        {"foo": {"bar": "12ab34"}},
        {"foo": {"bar": "12ab34", "foo": "ab"}},
        {
            "resolve_mapping_dict.yml": {
                "body": {"ab": {"foo": "ab"}, "de": {"foo": "de", "bar": "de"}}
            }
        },
        id="resolve a mapping value from a file and merge it into the target",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to_resolve": "something hello1"},
        {"to_resolve": "something hello1"},
        id="resolve_list is case-sensitive by default",
    ),
    pytest.param(
        {
            "filter": r"to\.resolve.s\\ub",
            "generic_resolver": {
                "field_mapping": {r"to\.resolve.s\\ub": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to.resolve": {"s\\ub": "something HELLO1"}},
        {"to.resolve": {"s\\ub": "something HELLO1"}, "resolved": "Greeting"},
        id="an escaped dotted field name is resolved correctly",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-zA-Z]+)\d*",
                },
            },
        },
        {"to_resolve": "Ab"},
        {"to_resolve": "Ab"},
        {"resolve_mapping.yml": {"body": {"ab": "ab_server_type", "de": "de_server_type"}}},
        id="resolve_from_file is case-sensitive by default",
    ),
    pytest.param(
        {
            "filter": "to_resolve_1 AND to_resolve_2",
            "generic_resolver": {
                "field_mapping": {
                    "to_resolve_1": "resolved_1",
                    "to_resolve_2": "resolved_2",
                },
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "resolve_list": {"fg": "fg_server_type"},
            },
        },
        {"to_resolve_1": "ab", "to_resolve_2": "fg"},
        {
            "to_resolve_1": "ab",
            "to_resolve_2": "fg",
            "resolved_1": "ab_server_type",
            "resolved_2": "fg_server_type",
        },
        {"resolve_mapping.yml": {"body": {"ab": "ab_server_type", "de": "de_server_type"}}},
        id="resolve_from_file and resolve_list combined for different fields",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": ["ab_server_type"]},
        {"resolve_mapping.yml": {"body": {"ab": "ab_server_type", "de": "de_server_type"}}},
        id="merge_with_target wraps a new resolved value in a list",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve_mapping.yml",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "merge_with_target": True,
            },
        },
        {"to_resolve": "12ab34", "resolved": ["aa_server_type"]},
        {"to_resolve": "12ab34", "resolved": ["aa_server_type", "ab_server_type"]},
        {"resolve_mapping.yml": {"body": {"ab": "ab_server_type", "de": "de_server_type"}}},
        id="merge_with_target appends a new resolved value to an existing list",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"resolved.foo": "resolved"},
                "resolve_list": {"bar": {"baz": "test"}},
                "merge_with_target": True,
            },
        },
        {"to_resolve": "12ab34", "resolved": {"foo": "bar"}},
        {"to_resolve": "12ab34", "resolved": {"foo": "bar", "baz": "test"}},
        id="merge_with_target merges a resolved mapping into an existing dict",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {"12ab34": {"baz": "test"}},
            },
        },
        {"to_resolve": "12ab34", "resolved": "foo"},
        {
            "to_resolve": "12ab34",
            "resolved": "foo",
            "tags": ["_generic_resolver_failure"],
        },
        id="an existing destination field without overwrite_target causes a failure tag",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {"12ab34": {"baz": "test"}},
                "overwrite_target": True,
            },
        },
        {"to_resolve": "12ab34", "resolved": "foo"},
        {"to_resolve": "12ab34", "resolved": {"baz": "test"}},
        id="overwrite_target replaces an existing destination field",
    ),
    pytest.param(
        {
            "filter": "to.resolve",
            "generic_resolver": {
                "field_mapping": {"to.resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to": {"resolve": "something no"}},
        {"to": {"resolve": "something no"}},
        id="a dotted source field without a match is left untouched",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "re.solved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
            },
        },
        {"to_resolve": "something no"},
        {"to_resolve": "something no"},
        id="a dotted destination field without a match is left untouched",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
                "ignore_case": True,
            },
        },
        {"to_resolve": "something HELLO1"},
        {"to_resolve": "something HELLO1", "resolved": "Greeting"},
        id="ignore_case still matches the original case in resolve_list",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting"},
                "ignore_case": True,
            },
        },
        {"to_resolve": "something hello1"},
        {"to_resolve": "something hello1", "resolved": "Greeting"},
        id="ignore_case matches a different case in resolve_list",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting", ".*BYE\\d": "Farewell"},
            },
        },
        {"to_resolve": "something HELLO1"},
        {"to_resolve": "something HELLO1", "resolved": "Greeting"},
        id="the first of several independent resolve_list patterns can match",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {".*HELLO\\d": "Greeting", ".*BYE\\d": "Farewell"},
            },
        },
        {"to_resolve": "something BYE1"},
        {"to_resolve": "something BYE1", "resolved": "Farewell"},
        id="the second of several independent resolve_list patterns can match",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve.json",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {"resolve.json": {"body": {"ab": "ab_server_type"}}},
        id="content_field defaults to the mapping root when omitted",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve.txt",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {"resolve.txt": {"body": {"content": {"ab": "ab_server_type"}}}},
        id="content_field works regardless of the file's suffix",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve.json",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "b",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "from_b"},
        {"resolve.json": {"body": {"a": {"ab": "from_a"}, "b": {"ab": "from_b"}}}},
        id="content_field selects among multiple sibling keys",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve.json",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
                "ignore_case": True,
            },
        },
        {"to_resolve": "12AB34"},
        {"to_resolve": "12AB34", "resolved": "ab_server_type"},
        {"resolve.json": {"body": {"content": {"ab": "ab_server_type"}}}},
        id="content_field works together with ignore_case",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "resolve.json",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {
            "resolve.json": {
                "body": {"content": [{"ab": "ab_server_type"}, {"de": "de_server_type"}]}
            }
        },
        id="content_field also accepts a list of single-key mappings",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": "http://localhost/resolve-mapping-text-plain",
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        },
        {"to_resolve": "12ab34"},
        {"to_resolve": "12ab34", "resolved": "ab_server_type"},
        {
            "http://localhost/resolve-mapping-text-plain": {
                "body": {"content": {"ab": "ab_server_type"}},
                "content_type": "text/plain",
            }
        },
        id="content_field also works when the server sends text/plain",
    ),
)

# rule, context, error_message
failure_test_cases = [
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": CONTENT_FIELD_URL,
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        },
        {CONTENT_FIELD_URL: {"body": ["ab", "de"]}},
        "Expected mapping type when content_field is set",
        id="content_field set but content root is a list",
    ),
    pytest.param(
        {
            "filter": "to_resolve",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": CONTENT_FIELD_URL,
                    "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "missing",
            },
        },
        {CONTENT_FIELD_URL: {"body": {"content": {"ab": "ab_server_type"}}}},
        "Error loading additions",
        id="content_field key absent from the loaded mapping",
    ),
]


class TestGenericResolver(BaseProcessorTestCase):
    CONFIG = {
        "type": "generic_resolver",
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
        self._load_rule(
            {
                "filter": "anything",
                "generic_resolver": {"field_mapping": {}},
            }
        )
        assert isinstance(self.object, GenericResolver)

    @pytest.mark.parametrize("rule, event, expected, context", test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)

        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)

        assert event == expected

    @pytest.mark.parametrize("rule, context, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, rule, context, error_message, provision_context):
        provision_context(context)

        with pytest.raises(InvalidConfigurationError, match=error_message):
            self._load_rule(rule)

    @pytest.mark.parametrize(["resolve_value"], field_value_test_cases)
    def test_resolve_not_dotted_field_no_conflict_different_values_match(self, resolve_value):
        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".*HELLO\\d": resolve_value},
                },
            }
        )

        expected = {"to_resolve": "something HELLO1", "resolved": resolve_value}
        document = {"to_resolve": "something HELLO1"}

        self.object.process(document)

        assert document == expected

    @pytest.mark.parametrize(["resolve_value"], field_value_test_cases)
    def test_resolve_not_dotted_field_no_conflict_different_values_match_from_file(
        self, resolve_value, tmp_path
    ):
        resolve_file_path = tmp_path / "rule.json"

        resolve_dict = {"abc": resolve_value}
        expected = {"to_resolve": "abc", "resolved": resolve_value}
        document = {"to_resolve": "abc"}

        with open(resolve_file_path, mode="w+", encoding="utf8") as stream:
            stream.write(json.dumps(resolve_dict))

        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": {
                        "path": str(resolve_file_path),
                        "pattern": r"(?P<mapping>.+)",
                    },
                },
            }
        )

        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict(
        self,
    ):
        self._load_rule(
            {
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
        )

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}

        document = {"to_resolve": "12ab34"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict_and_diff_inputs(
        self,
    ):
        self._load_rule(
            {
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
        )

        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_server_type", "de_server_type"],
        }

        document = {"to_resolve": "12ab34", "other_to_resolve": "00de11"}

        self.object.process(document)
        self.object.process(document)

        assert document == expected

    @responses.activate
    def test_resolve_from_http(self, tmp_path):
        target = "localhost:123"
        url = f"http://{target}"

        responses.add(responses.GET, url, json={"ab": {"new1": "1"}})
        responses.add(responses.GET, url, json={"ab": {"new1": "1", "new2": "2"}})

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            scheduler = HttpGetter(protocol="http", target=url).scheduler
            self._load_rule(
                {
                    "filter": "to_resolve",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_from_file": {
                            "path": url,
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "overwrite_target": True,
                    },
                }
            )

            expected_1 = {"to_resolve": "12ab34", "resolved": {"new1": "1"}}
            expected_2 = {"to_resolve": "12ab34", "resolved": {"new1": "1", "new2": "2"}}
            document = {"to_resolve": "12ab34"}

            self.object.setup()

            self.object.process(document)
            assert document == expected_1

            HttpGetter.refresh()  # Try refresh, but no time to update yet
            self.object.process(document)
            assert document == expected_1

            scheduler.run_all()  # Force update
            self.object.process(document)
            assert document == expected_2

    def test_resolve_dotted_src_and_dest_field_and_conflict_match(self):
        self._load_rule(
            {
                "filter": "to.resolve",
                "generic_resolver": {
                    "field_mapping": {"to.resolve": "re.solved"},
                    "resolve_list": {".*HELLO\\d": "Greeting"},
                },
            }
        )
        document = {
            "to": {"resolve": "something HELLO1"},
            "re": {"solved": "I already exist!"},
        }
        expected = {
            "tags": ["_generic_resolver_failure"],
            "to": {"resolve": "something HELLO1"},
            "re": {"solved": "I already exist!"},
        }
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_resolve_from_cache_with_large_enough_cache(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        event = {"to_resolve": "foo"}
        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        self.object.process(event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        self.object.process(event)

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        self.object.process({"to_resolve": "bar"})

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 4

    def test_resolve_from_cache_with_cache_smaller_than_results(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 1
        self.object = Factory.create({"generic_resolver": config})

        event = {"to_resolve": "foo"}
        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        self.object.process(event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        self.object.process(event)

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        self.object.process({"to_resolve": "bar"})

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 3

    def test_resolve_without_cache(self):
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 0
        self.object = Factory.create({"generic_resolver": config})

        event = {"to_resolve": "foo"}
        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        self.object.process(event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        self.object.process(event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        self.object.process({"to_resolve": "bar"})

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

    def test_resolve_from_cache_with_update_interval(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["cache_metrics_interval"] = 2
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        event = {"to_resolve": "foo"}
        other_event = {"to_resolve": "bar"}
        self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        self.object.process(event)

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        self.object.process(event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        self.object.process(other_event)

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        self.object.process(other_event)

        assert self.object.metrics.new_results == 3
        assert self.object.metrics.cached_results == 3
        assert self.object.metrics.num_cache_entries == 3
