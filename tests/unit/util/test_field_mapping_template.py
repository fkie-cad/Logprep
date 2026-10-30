"""Field mapping templates compile configuration and evaluate event context."""

from collections.abc import Collection
from copy import deepcopy

import pytest

from logprep.util import field_mapping_template
from logprep.util.field_mapping_template import (
    Call,
    Constant,
    FieldMappingTemplate,
    FieldMappingTemplateConfigError,
    FieldMappingTemplateEvaluationError,
    Function,
    ParsedCall,
)
from logprep.util.helper import FieldValue, JsonObject

STATIC_CONTEXT: dict[str, JsonObject] = {
    "rule": {
        "description": "Example rule",
        "id": 42,
        "optional": None,
        "defaults": {"tags": ["example"]},
    }
}
RUNTIME_CONTEXT: dict[str, JsonObject] = {
    "source_event": {
        "@timestamp": "2026-10-27T12:00:00Z",
        "event": {"id": 123, "id ": 456, "id|": 789, "a.b": "literal dot"},
        "optional": None,
        "enabled": False,
        "items": ["first", "second"],
        "back\\slash": "backslash field",
        "closing}": "closing brace field",
    }
}
RUNTIME_ROOTS: Collection[str] = {"source_event", "target_event"}


def _assert_value_types(actual: FieldValue, expected: FieldValue) -> None:
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        for key, value in expected.items():
            _assert_value_types(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list)
        for actual_value, expected_value in zip(actual, expected):
            _assert_value_types(actual_value, expected_value)


@pytest.mark.parametrize(
    ["mapping", "expected"],
    [
        pytest.param(
            {"text": "hello", "empty": "", "space": "  \t "},
            {"text": "hello", "empty": "", "space": "  \t "},
            id="literal_strings",
        ),
        pytest.param(
            {"int": 7, "float": 1.5, "bool": False, "null": None},
            {"int": 7, "float": 1.5, "bool": False, "null": None},
            id="literal_scalar_types",
        ),
        pytest.param({}, {}, id="empty_root"),
        pytest.param(
            {"${rule.description}": "${rule.id}"},
            {"Example rule": 42},
            id="static_key_and_value",
        ),
        pytest.param(
            {"${source_event.items.0}": "${source_event.event.id}"},
            {"first": 123},
            id="runtime_key_and_value",
        ),
        pytest.param(
            {"${rule.id | str}": "${source_event.event.id}"},
            {"42": 123},
            id="converted_static_key_runtime_value",
        ),
        pytest.param(
            {"${source_event.event.id | str}": "${rule.id}"},
            {"123": 42},
            id="converted_runtime_key_static_value",
        ),
        pytest.param(
            {"nested": [{"${rule.description}": {"${source_event.items.0}": 1}}]},
            {"nested": [{"Example rule": {"first": 1}}]},
            id="keys_in_nested_mapping_and_list",
        ),
        pytest.param(
            {r"\${source_event.event.id}": 1, r"back\\slash": 2, "": 3},
            {"${source_event.event.id}": 1, "back\\slash": 2, "": 3},
            id="escaped_and_empty_literal_keys",
        ),
        pytest.param(
            {r"${source_event.event.a\.b}": 1},
            {"literal dot": 1},
            id="escaped_path_in_key",
        ),
        pytest.param(
            {"items": [{"${rule.description}": 1}, {"${rule.description}": 2}]},
            {"items": [{"Example rule": 1}, {"Example rule": 2}]},
            id="same_key_in_separate_mappings",
        ),
        pytest.param({"dict": {}, "list": []}, {"dict": {}, "list": []}, id="empty_containers"),
        pytest.param(
            {"nested": [{"value": [1, True, None]}, []]},
            {"nested": [{"value": [1, True, None]}, []]},
            id="nested_static_containers",
        ),
        pytest.param(
            {"value": "${rule.description}"},
            {"value": "Example rule"},
            id="static_lookup",
        ),
        pytest.param({"value": "${rule.optional}"}, {"value": None}, id="static_null_is_present"),
        pytest.param({"value": "${rule.id | str}"}, {"value": "42"}, id="static_conversion"),
        pytest.param(
            {"value": ["${rule.defaults}", {"id": "${rule.id}"}]},
            {"value": [{"tags": ["example"]}, {"id": 42}]},
            id="static_lookups_in_containers",
        ),
        pytest.param(
            {"value": "${source_event.@timestamp}"},
            {"value": "2026-10-27T12:00:00Z"},
            id="timestamp_is_an_ordinary_field",
        ),
        pytest.param(
            {"value": "${source_event.event.id}"},
            {"value": 123},
            id="runtime_lookup_preserves_integer",
        ),
        pytest.param(
            {"value": "${source_event.enabled}"},
            {"value": False},
            id="runtime_lookup_preserves_boolean",
        ),
        pytest.param(
            {"value": "${source_event.optional}"},
            {"value": None},
            id="runtime_null_is_present",
        ),
        pytest.param(
            {"value": "${source_event.event.id|str}"}, {"value": "123"}, id="runtime_conversion"
        ),
        pytest.param(
            {"value": "${source_event.event.id | str | str()}"},
            {"value": "123"},
            id="chained_functions",
        ),
        pytest.param(
            {"${str(rule.id)}": ["${str(source_event.event.id)}"]},
            {"42": ["123"]},
            id="function_key_and_list_value",
        ),
        pytest.param(
            {"value": "${source_event.event.id | str }"},
            {"value": "123"},
            id="conversion_with_spaces",
        ),
        pytest.param(
            {"value": "${source_event.event.id\t|\tstr\t}"},
            {"value": "123"},
            id="conversion_with_tabs",
        ),
        pytest.param(
            {"value": [{"id": "${source_event.event.id}"}, ["${rule.id}", 1]]},
            {"value": [{"id": 123}, [42, 1]]},
            id="mixed_nested_containers",
        ),
        pytest.param(
            {"static": "${rule.id}", "dynamic": "${source_event.event.id}"},
            {"static": 42, "dynamic": 123},
            id="mixed_static_and_runtime_mapping",
        ),
        pytest.param(
            {
                "rule": {
                    "${rule.description}": "${rule.id | str}",
                    "defaults": "${rule.defaults}",
                },
                "events": [
                    {
                        "${source_event.event.id | str}": {
                            "timestamp": "${source_event.@timestamp}",
                            "items": "${source_event.items}",
                            "text": "${source_event.items | str}",
                            "enabled": "${source_event.enabled}",
                            "optional": "${source_event.optional}",
                            "literal": r"\${source_event.items}",
                        }
                    },
                    ["${rule.id}", "${source_event.items.0}", 1, None],
                ],
            },
            {
                "rule": {"Example rule": "42", "defaults": {"tags": ["example"]}},
                "events": [
                    {
                        "123": {
                            "timestamp": "2026-10-27T12:00:00Z",
                            "items": ["first", "second"],
                            "text": "['first', 'second']",
                            "enabled": False,
                            "optional": None,
                            "literal": "${source_event.items}",
                        }
                    },
                    [42, "first", 1, None],
                ],
            },
            id="complete_nested_mapping",
        ),
        pytest.param(
            {"literal": r"\${source_event.event.id}", "slash": r"\\"},
            {"literal": "${source_event.event.id}", "slash": "\\"},
            id="escaped_expression_and_backslash",
        ),
        pytest.param({"value": r"${source_event.event.id\ }"}, {"value": 456}, id="escaped_space"),
        pytest.param(
            {"value": r"${source_event.event.a\.b}"},
            {"value": "literal dot"},
            id="escaped_dot",
        ),
        pytest.param(
            {"value": r"${source_event.back\\slash}"},
            {"value": "backslash field"},
            id="escaped_backslash",
        ),
        pytest.param(
            {"value": r"${source_event.closing\}}"},
            {"value": "closing brace field"},
            id="escaped_closing_brace",
        ),
        pytest.param({"value": "${source_event.items.1}"}, {"value": "second"}, id="list_index"),
        pytest.param(
            {"value": r"${source_event.event.id\||str}"},
            {"value": "789"},
            id="escaped_pipe_before_conversion",
        ),
    ],
)
def test_compile_and_evaluate(mapping: JsonObject, expected: JsonObject) -> None:
    template = FieldMappingTemplate.compile(
        deepcopy(mapping),
        static_context=deepcopy(STATIC_CONTEXT),
        runtime_roots=RUNTIME_ROOTS,
    )

    actual = template.evaluate(runtime_context=deepcopy(RUNTIME_CONTEXT))

    assert actual == expected
    _assert_value_types(actual, expected)


@pytest.mark.parametrize(
    ["mapping", "runtime_roots", "expected_exception", "match"],
    [
        pytest.param(
            {"nested": [{"${unknown.name}": 1}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Unknown context root",
            id="key_unknown_root",
        ),
        pytest.param(
            {"${rule.missing}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Cannot resolve lookup path",
            id="key_missing_static_field",
        ),
        pytest.param(
            {"nested": [{"${rule.missing | str}": 1}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Cannot resolve lookup path",
            id="key_missing_nested_converted_static_field",
        ),
        pytest.param(
            {"prefix ${rule.id}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "interpolation is not supported",
            id="key_interpolation",
        ),
        pytest.param(
            {"${rule.id": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Unclosed expression",
            id="key_unclosed_expression",
        ),
        pytest.param(
            {"${rule.id}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Mapping keys must resolve to strings",
            id="key_static_int",
        ),
        pytest.param(
            {"${rule.optional}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Mapping keys must resolve to strings",
            id="key_static_null",
        ),
        pytest.param(
            {"${rule.defaults}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Mapping keys must resolve to strings",
            id="key_static_dict",
        ),
        pytest.param(
            {"${rule.defaults.tags}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Mapping keys must resolve to strings",
            id="key_static_list",
        ),
        pytest.param(
            {"${source_event.event.id}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Mapping keys must resolve to strings",
            id="key_runtime_int",
        ),
        pytest.param(
            {"${source_event.enabled}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Mapping keys must resolve to strings",
            id="key_runtime_bool",
        ),
        pytest.param(
            {"${source_event.optional}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Mapping keys must resolve to strings",
            id="key_runtime_null",
        ),
        pytest.param(
            {"${source_event.event}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Mapping keys must resolve to strings",
            id="key_runtime_dict",
        ),
        pytest.param(
            {"${source_event.items}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Mapping keys must resolve to strings",
            id="key_runtime_list",
        ),
        pytest.param(
            {"${target_event.name}": 1},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Missing runtime context root",
            id="key_missing_runtime_root",
        ),
        pytest.param(
            {"nested": [{"${source_event.missing}": 1}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Cannot resolve lookup path",
            id="key_missing_runtime_field",
        ),
        pytest.param(
            {"name": 1, r"\name": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_escaped_literal",
        ),
        pytest.param(
            {"${rule.description}": 1, "Example rule": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_static",
        ),
        pytest.param(
            {"${rule.id|str}": 1, "${rule.id | str}": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_equivalent_expressions",
        ),
        pytest.param(
            {"${source_event.items.0}": 1, "first": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_runtime",
        ),
        pytest.param(
            {"${source_event.event.id | str}": 1, "123": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_converted",
        ),
        pytest.param(
            {"${rule.description}": "${source_event.event.id}", "Example rule": 2},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_static_keys_runtime_value",
        ),
        pytest.param(
            {"nested": [{"name": 1, r"\name": 2}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Duplicate resolved mapping key",
            id="key_collision_nested_in_list",
        ),
        pytest.param(
            {"value": "text\\"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Trailing backslash at position 4",
            id="trailing_backslash",
        ),
        pytest.param(
            {"value": "${source_event.id"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Unclosed expression at position 0",
            id="unclosed_expression",
        ),
        pytest.param(
            {"value": "${source_event.${id}}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Nested expression at position 15",
            id="nested_expression",
        ),
        pytest.param(
            {"value": "${}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected a lookup or function call",
            id="empty_expression",
        ),
        pytest.param(
            {"value": "${source_event}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected at least one field name",
            id="root_without_field",
        ),
        pytest.param(
            {"value": "${source_event..id}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected TEXT",
            id="empty_path_segment",
        ),
        pytest.param(
            {"value": "${source_event.id.}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected TEXT",
            id="trailing_dot",
        ),
        pytest.param(
            {"value": "${source_event. id}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected TEXT",
            id="space_after_dot",
        ),
        pytest.param(
            {"value": "${source_event.id|}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected TEXT",
            id="empty_conversion",
        ),
        pytest.param(
            {"value": "${source_event.id|unknown}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Unknown function 'unknown'",
            id="unknown_conversion",
        ),
        pytest.param(
            {"value": "${source_event.id|str|}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected TEXT",
            id="missing_function_after_second_pipe",
        ),
        pytest.param(
            {"value": "${ 24 }"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected a lookup or function call",
            id="bare_integer_is_not_an_expression",
        ),
        pytest.param(
            {"value": '${ "hello world" }'},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Expected a lookup or function call",
            id="bare_string_is_not_an_expression",
        ),
        pytest.param(
            {"value": "prefix ${source_event.id}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "interpolation is not supported",
            id="prefixed_expression",
        ),
        pytest.param(
            {"value": "${source_event.id}suffix"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "after the expression",
            id="suffix_after_lookup",
        ),
        pytest.param(
            {"value": "${source_event.id|str}suffix"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "after the expression",
            id="suffix_after_conversion",
        ),
        pytest.param(
            {"value": "${source_event.id|str}${rule.id}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "after the expression",
            id="second_expression",
        ),
        pytest.param(
            {"value": "${unknown.id}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Unknown context root 'unknown'",
            id="unknown_root",
        ),
        pytest.param(
            {"value": "${rule.missing}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "in static context root 'rule'",
            id="missing_static_field",
        ),
        pytest.param(
            {"value": "${rule.id.child}"},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "in static context root 'rule'",
            id="static_scalar_traversal",
        ),
        pytest.param(
            {"nested": [{"value": "${rule.missing|str}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "in static context root 'rule'",
            id="validation_visits_nested_conversion",
        ),
        pytest.param(
            {},
            {"rule"},
            FieldMappingTemplateConfigError,
            "overlapping roots: .*rule",
            id="overlapping_roots_even_without_lookups",
        ),
        pytest.param(
            [],
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Template root must be a mapping",
            id="root_must_be_mapping",
        ),
        pytest.param(
            {"nested": [{1: "value"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateConfigError,
            "Mapping keys must be strings",
            id="nested_mapping_key_must_be_string",
        ),
        pytest.param(
            {"nested": [{"value": "${target_event.id}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "Missing runtime context root 'target_event'",
            id="missing_runtime_root",
        ),
        pytest.param(
            {"nested": [{"value": "${source_event.missing}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "in runtime context root 'source_event'",
            id="missing_runtime_field",
        ),
        pytest.param(
            {"nested": [{"value": "${source_event.missing|str}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "in runtime context root 'source_event'",
            id="missing_converted_field",
        ),
        pytest.param(
            {"nested": [{"value": "${source_event.event.id.child}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "in runtime context root 'source_event'",
            id="runtime_scalar_traversal",
        ),
        pytest.param(
            {"nested": [{"value": "${source_event.items.99}"}]},
            RUNTIME_ROOTS,
            FieldMappingTemplateEvaluationError,
            "in runtime context root 'source_event'",
            id="runtime_index_out_of_bounds",
        ),
    ],
)
def test_compile_and_evaluate_errors(
    mapping,
    runtime_roots: Collection[str],
    expected_exception: type[Exception],
    match: str,
) -> None:
    static_context = deepcopy(STATIC_CONTEXT)
    runtime_context = deepcopy(RUNTIME_CONTEXT)

    if expected_exception is FieldMappingTemplateConfigError:
        with pytest.raises(expected_exception, match=match):
            FieldMappingTemplate.compile(
                deepcopy(mapping), static_context=static_context, runtime_roots=runtime_roots
            )
    else:
        template = FieldMappingTemplate.compile(
            deepcopy(mapping), static_context=static_context, runtime_roots=runtime_roots
        )
        with pytest.raises(expected_exception, match=match):
            template.evaluate(runtime_context=runtime_context)


@pytest.mark.parametrize("foldable", [False, True])
@pytest.mark.parametrize(
    ["expression", "expected", "constant", "call_count"],
    [
        pytest.param("${f(42)}", 42, True, 1, id="integer_argument"),
        pytest.param("${f(-20)}", -20, True, 1, id="negative_integer"),
        pytest.param("${f(+20)}", 20, True, 1, id="positive_sign"),
        pytest.param("${f(123_456)}", 123456, True, 1, id="integer_separators"),
        pytest.param("${f(1.25)}", 1.25, True, 1, id="float_argument"),
        pytest.param("${f(-1.25)}", -1.25, True, 1, id="negative_float"),
        pytest.param("${f(1e3)}", 1000.0, True, 1, id="scientific_integer"),
        pytest.param("${f(1.5E-3)}", 0.0015, True, 1, id="signed_exponent"),
        pytest.param("${f(1_234.5_6)}", 1234.56, True, 1, id="float_separators"),
        pytest.param("${f(true)}", True, True, 1, id="true_argument"),
        pytest.param("${f(False)}", False, True, 1, id="title_case_false"),
        pytest.param("${f(none)}", None, True, 1, id="none_argument"),
        pytest.param("${f(None)}", None, True, 1, id="title_case_none"),
        pytest.param('${f("123")}', "123", True, 1, id="quoted_number"),
        pytest.param("${f('false')}", "false", True, 1, id="quoted_boolean"),
        pytest.param('${f("")}', "", True, 1, id="empty_string"),
        pytest.param(
            '${f("} ${nested} | (),=.")}',
            "} ${nested} | (),=.",
            True,
            1,
            id="quoted_delimiters",
        ),
        pytest.param(r"""${f("a\"b\\c")}""", 'a"b\\c', True, 1, id="escaped_double_quote"),
        pytest.param(r"${f('a\'b')}", "a'b", True, 1, id="escaped_single_quote"),
        pytest.param("${f()}", None, True, 1, id="zero_arguments"),
        pytest.param("${f( )}", None, True, 1, id="empty_argument_whitespace"),
        pytest.param("${f(rule.id)}", 42, True, 1, id="static_lookup"),
        pytest.param("${f(source_event.event.id)}", 123, False, 1, id="runtime_lookup"),
        pytest.param("${f(source_event.items.0)}", "first", False, 1, id="numeric_path_segment"),
        pytest.param("${f(value=rule.id)}", 42, True, 1, id="static_kwargs_only"),
        pytest.param("${f(value=source_event.event.id)}", 123, False, 1, id="runtime_kwargs_only"),
        pytest.param(
            "${f(source_event.event.id, other=rule.id)}", [123, 42], False, 1, id="mixed_arguments"
        ),
        pytest.param(
            "${f(rule.id, other=source_event.event.id)}", [42, 123], False, 1, id="runtime_keyword"
        ),
        pytest.param("${f( value  =  rule.id )}", 42, True, 1, id="keyword_whitespace"),
        pytest.param("${f(f(rule.id))}", 42, True, 2, id="nested_static_calls"),
        pytest.param("${f(f(source_event.event.id))}", 123, False, 2, id="nested_runtime_calls"),
        pytest.param(
            "${source_event.event.id | f(other=rule.id)}", [123, 42], False, 1, id="piped_keyword"
        ),
        pytest.param("${source_event.event.id | f | str()}", "123", False, 1, id="pipe_chain"),
        pytest.param(
            "${f(value=source_event.event.id | str)}", "123", False, 1, id="pipe_in_argument"
        ),
        pytest.param("${str(f())}", "None", True, 1, id="outer_foldable_inner_dynamic"),
    ],
)
def test_function_calls(
    expression: str, expected: FieldValue, constant: bool, call_count: int, foldable: bool
) -> None:
    calls: list[tuple[FieldValue, FieldValue]] = []

    def f(value: FieldValue = None, other: FieldValue = None) -> FieldValue:
        calls.append((value, other))
        return value if other is None else [value, other]

    template = FieldMappingTemplate.compile(
        {"nested": [{"value": expression}]},
        static_context=deepcopy(STATIC_CONTEXT),
        runtime_roots=RUNTIME_ROOTS,
        functions={
            "f": Function(f, foldable=foldable),
            "str": Function(lambda x: str(x), can_borrow_input=True, foldable=True),
        },
    )
    folded = constant and foldable
    assert len(calls) == (call_count if folded else 0)
    assert isinstance(template.root_operation, Constant) is folded

    for _ in range(2):
        actual = template.evaluate(runtime_context=deepcopy(RUNTIME_CONTEXT))
        expected_mapping: JsonObject = {"nested": [{"value": expected}]}
        assert actual == expected_mapping
        _assert_value_types(actual, expected_mapping)

    assert len(calls) == call_count * (1 if folded else 2)


@pytest.mark.parametrize(
    ["expression", "phase", "expected_exception", "match"],
    [
        pytest.param(
            "${str()}",
            "compile",
            FieldMappingTemplateConfigError,
            "Invalid arguments.*missing",
            id="missing_argument",
        ),
        pytest.param(
            "${str(1, 2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Invalid arguments.*too many positional",
            id="extra_argument",
        ),
        pytest.param(
            "${str(other=1)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Invalid arguments",
            id="unsupported_keyword",
        ),
        pytest.param(
            "${rule.id | str(x=2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Invalid arguments.*multiple values",
            id="pipe_keyword_collision",
        ),
        pytest.param(
            "${str(x=1, x=2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Duplicate keyword argument",
            id="duplicate_keyword",
        ),
        pytest.param(
            "${str(a-b=1)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Invalid keyword argument name",
            id="invalid_keyword",
        ),
        pytest.param(
            "${str(x=1, 2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Positional arguments must precede",
            id="positional_after_keyword",
        ),
        pytest.param(
            "${str(1,)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected a literal",
            id="trailing_comma",
        ),
        pytest.param(
            "${str(,1)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected a literal",
            id="leading_comma",
        ),
        pytest.param(
            "${str(1 2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected COMMA",
            id="missing_comma",
        ),
        pytest.param(
            "${str(x=)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected a literal",
            id="missing_keyword_value",
        ),
        pytest.param(
            "${str(1}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected COMMA",
            id="missing_parenthesis",
        ),
        pytest.param(
            "${str (1)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected at least one field",
            id="space_before_parenthesis",
        ),
        pytest.param(
            "${rule.id | str (2)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Expected EXPRESSION_END",
            id="piped_space_before_parenthesis",
        ),
        pytest.param(
            "${str(unknown.id)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Unknown context root",
            id="nested_unknown_lookup",
        ),
        pytest.param(
            "${str(x=rule.missing)}",
            "compile",
            FieldMappingTemplateConfigError,
            "Cannot resolve lookup path",
            id="missing_static_keyword",
        ),
        pytest.param(
            '${str("unfinished)}',
            "compile",
            FieldMappingTemplateConfigError,
            "Unclosed string",
            id="unclosed_string",
        ),
        pytest.param(
            "${str()}",
            "validation",
            RuntimeError,
            "resolved Call.*during validation",
            id="compiled_node_in_validation",
        ),
        pytest.param(
            "${str()}",
            "compilation",
            RuntimeError,
            "resolved Call.*during compilation",
            id="compiled_node_in_compilation",
        ),
        pytest.param(
            "${str()}",
            "evaluation",
            RuntimeError,
            "unresolved ParsedCall.*during evaluation",
            id="parsed_node_in_evaluation",
        ),
    ],
)
def test_function_errors(
    expression: str, phase: str, expected_exception: type[Exception], match: str
) -> None:
    with pytest.raises(expected_exception, match=match):
        if phase == "compile":
            FieldMappingTemplate.compile(
                {"value": expression}, static_context=STATIC_CONTEXT, runtime_roots=RUNTIME_ROOTS
            )
        elif phase == "validation":
            field_mapping_template._validate_operation(Call(Function(str), (), {}), {}, (), {})
        elif phase == "compilation":
            field_mapping_template._compile_operation(Call(Function(str), (), {}), {}, {})
        else:
            field_mapping_template._evaluate_operation(ParsedCall("str", (), {}), {})
