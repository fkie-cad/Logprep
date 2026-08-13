# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase


def rule(config: dict) -> dict:
    return {
        "filter": "test",
        "field_name_replacer": {
            "source_fields": ["test"],
            "to_replace": ".",
            "replacement": "__",
            **config,
        },
    }


DEFAULT_RULE = {
    "filter": "message",
    "field_name_replacer": {
        "source_fields": ["message"],
        "to_replace": ".",
        "replacement": "__",
    },
    "description": "Replace dots in field names below message.",
}


example_test_cases = [
    pytest.param(
        rule({}),
        {"test": {"k8s.application/kind": "value"}},
        {"test": {"k8s__application/kind": "value"}},
        id="replaces dots in nested field keys",
    ),
    pytest.param(
        rule({}),
        {"test": {"nested": {"k8s.application/kind": "value"}}},
        {"test": {"nested": {"k8s__application/kind": "value"}}},
        id="recursively replaces characters by default",
    ),
    pytest.param(
        rule({"collision_strategy": "merge"}),
        {"test": {"k8s.application": ["incoming"], "k8s__application": ["existing"]}},
        {"test": {"k8s__application": ["incoming", "existing"]}},
        id="merges colliding lists by appending",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        rule({"collapse_sequences": True}),
        {"test": {"k8s...application": "value"}},
        {"test": {"k8s__application": "value"}},
        id="collapses consecutive characters when configured",
    ),
    pytest.param(
        rule({"to_replace": "*", "collapse_sequences": True}),
        {"test": {"k8s***application": "value"}},
        {"test": {"k8s__application": "value"}},
        id="treats regex metacharacters as literal characters when collapsing",
    ),
    pytest.param(
        rule({"to_replace": "ab", "collapse_sequences": True}),
        {"test": {"k8sababapplication": "value"}},
        {"test": {"k8s__application": "value"}},
        id="collapses repeated multi-character strings",
    ),
    pytest.param(
        rule({"to_replace": ["ab", "cd"], "collapse_sequences": True}),
        {"test": {"abcd": "value"}},
        {"test": {"__": "value"}},
        id="collapses adjacent configured sequences",
    ),
    pytest.param(
        rule({"to_replace": ["a", "ab"], "collapse_sequences": True}),
        {"test": {"ab": "value"}},
        {"test": {"__": "value"}},
        id="matches the longest overlapping configured sequence",
    ),
    pytest.param(
        rule({"to_replace": [".", "/"], "collapse_sequences": True}),
        {"test": {"k8s././application": "value"}},
        {"test": {"k8s__application": "value"}},
        id="collapses adjacent configured characters",
    ),
    pytest.param(
        rule({"replacement": r"\_"}),
        {"test": {"k8s.application": "value"}},
        {"test": {r"k8s\_application": "value"}},
        id="keeps backslashes in the replacement literal",
    ),
    pytest.param(
        rule({"strip_prefix": True, "strip_suffix": True}),
        {"test": {".k8s.application.": "value"}},
        {"test": {"k8s__application": "value"}},
        id="strips leading and trailing characters when configured",
    ),
    pytest.param(
        rule({"to_replace": ["ab", "cd"], "strip_prefix": True, "strip_suffix": True}),
        {"test": {"bacontentdc": "value"}},
        {"test": {"bacontentdc": "value"}},
        id="does not strip individual characters from configured strings",
    ),
    pytest.param(
        rule({"to_replace": [".", "/"]}),
        {"test": {"k8s.application/kind": "value"}},
        {"test": {"k8s__application__kind": "value"}},
        id="replaces each configured character",
    ),
    pytest.param(
        rule({"source_fields": ["missing"]}),
        {"test": {"k8s.application/kind": "value"}},
        {"test": {"k8s.application/kind": "value"}},
        id="ignores a missing source field",
    ),
    pytest.param(
        rule({"source_fields": ["test.value"]}),
        {"test": {"value": "k8s.application/kind"}},
        {"test": {"value": "k8s.application/kind"}},
        id="ignores a source field whose value is not a dictionary",
    ),
    pytest.param(
        rule({"source_fields": ["test.value.child"]}),
        {"test": {"value": "scalar"}},
        {"test": {"value": "scalar"}},
        id="ignores a dotted source field below a scalar value",
    ),
    pytest.param(
        rule({}),
        {"test": [[[{"k8s.application/kind": "value"}]]]},
        {"test": [[[{"k8s__application/kind": "value"}]]]},
        id="recursively replaces field names in dictionaries nested in lists",
    ),
    pytest.param(
        rule({"collision_strategy": "merge"}),
        {
            "test": {
                "k8s__application": {"existing": "value", "same": "existing"},
                "k8s.application": {"incoming": "value", "same": "incoming"},
            }
        },
        {
            "test": {
                "k8s__application": {
                    "existing": "value",
                    "incoming": "value",
                    "same": "incoming",
                }
            }
        },
        id="merges colliding dictionaries with transformed values taking precedence",
    ),
    pytest.param(
        rule({"collision_strategy": "merge"}),
        {"test": {"k8s.application": "incoming", "k8s__application": ["existing"]}},
        {"test": {"k8s__application": ["incoming", "existing"]}},
        id="merges a scalar into a colliding list",
    ),
    pytest.param(
        rule({"collision_strategy": "merge"}),
        {"test": {"k8s.application": ["incoming"], "k8s__application": "existing"}},
        {"test": {"k8s__application": ["incoming", "existing"]}},
        id="merges a list with a colliding scalar",
    ),
    pytest.param(
        rule({"collision_strategy": "keep_incoming"}),
        {"test": {"k8s__application": "existing", "k8s.application": "incoming"}},
        {"test": {"k8s__application": "incoming"}},
        id="keeps the incoming transformed value when configured",
    ),
)


class TestFieldNameReplacer(BaseProcessorTestCase):
    CONFIG = {
        "type": "field_name_replacer",
        "rules": [DEFAULT_RULE],
    }

    @pytest.mark.parametrize("rule, event, expected, _context", test_cases)
    def test_replaces_characters_in_field_names(self, rule, event, expected, _context):
        self._load_rule(rule)

        result = self.object.process(event)

        assert not result.errors
        assert event == expected

    @pytest.mark.parametrize(
        "testcase, config, event",
        [
            (
                "raises for a colliding key by default",
                {},
                {"test": {"k8s.application": "incoming", "k8s__application": "existing"}},
            ),
            (
                "does not merge colliding scalar values",
                {"collision_strategy": "merge"},
                {"test": {"k8s.application": "incoming", "k8s__application": "existing"}},
            ),
            (
                "does not merge a dictionary into a colliding list",
                {"collision_strategy": "merge"},
                {
                    "test": {
                        "k8s.application": {"incoming": "value"},
                        "k8s__application": ["existing"],
                    }
                },
            ),
            (
                "does not merge a list into a colliding dictionary",
                {"collision_strategy": "merge"},
                {
                    "test": {
                        "k8s.application": ["incoming"],
                        "k8s__application": {"existing": "value"},
                    }
                },
            ),
            (
                "does not merge a scalar into a colliding dictionary",
                {"collision_strategy": "merge"},
                {
                    "test": {
                        "k8s.application": "incoming",
                        "k8s__application": {"existing": "value"},
                    }
                },
            ),
        ],
    )
    def test_rejects_unsupported_field_name_collisions(self, testcase, config, event):
        rule = {
            "filter": "test",
            "field_name_replacer": {
                "source_fields": ["test"],
                "to_replace": ".",
                "replacement": "__",
                **config,
            },
        }
        self._load_rule(rule)

        result = self.object.process(event)

        assert not result.errors, testcase
        assert len(result.warnings) == 1, testcase
        assert isinstance(result.warnings[0], FieldExistsWarning), testcase
