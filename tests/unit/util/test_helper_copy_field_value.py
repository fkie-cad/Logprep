# pylint: disable=missing-docstring
# pylint: disable=protected-access
import collections
import copy
import datetime
import math
import random
from typing import Any, Callable
from unittest import mock

import pytest

from logprep.util import helper
from logprep.util.helper import JsonObject, copy_field_value

INT64_MIN = -(2**63)
UINT64_MAX = 2**64 - 1


class Opaque:
    """An object msgspec cannot encode, comparable by value."""

    def __init__(self, payload: list[int]) -> None:
        self.payload = payload

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Opaque) and other.payload == self.payload

    __hash__ = None  # type: ignore[assignment]


@pytest.fixture(
    name="copy_function",
    params=[copy_field_value, helper._copy_field_value],
    ids=["copy_field_value", "pure_python_fallback"],
)
def fixture_copy_function(request: pytest.FixtureRequest) -> Callable[[Any], Any]:
    """Both implementations, so the fallback stays a drop-in for copy_field_value."""
    return request.param


def assert_identical(actual: Any, expected: Any) -> None:
    """Assert equal values with identical types, float signs, NaNs and key order."""
    assert type(actual) is type(expected), f"{type(actual)} is not {type(expected)}"
    if isinstance(expected, float):
        if math.isnan(expected):
            assert math.isnan(actual)
        else:
            assert actual == expected
            assert math.copysign(1.0, actual) == math.copysign(1.0, expected)
    elif isinstance(expected, dict):
        assert [(type(key), key) for key in actual] == [(type(key), key) for key in expected]
        for key, value in expected.items():
            assert_identical(actual[key], value)
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected):
            assert_identical(actual_item, expected_item)
    else:
        assert actual == expected


def container_ids(value: Any) -> set[int]:
    """Collect the ids of all dicts and lists reachable from value (cycle-safe)."""
    ids: set[int] = set()
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, (dict, list)) and id(current) not in ids:
            ids.add(id(current))
            stack.extend(current.values() if isinstance(current, dict) else current)
    return ids


def assert_independent(copied: Any, original: Any) -> None:
    """Assert that copy and original share no mutable container."""
    assert not container_ids(copied) & container_ids(original)


def assert_copied_like_deepcopy(copy_function: Callable[[Any], Any], value: Any) -> None:
    """Assert the copy matches deepcopy, shares no container and leaves the input unchanged."""
    expected = copy.deepcopy(value)  # snapshot first: a mutated input must not become the oracle
    result = copy_function(value)
    assert_identical(result, expected)
    assert_identical(value, expected)
    assert_independent(result, value)


def nested(depth: int, leaf: Any, kind: type = dict) -> Any:
    value = leaf
    for _ in range(depth):
        value = {"x": value} if kind is dict else [value]
    return value


def random_text(rng: random.Random) -> str:
    alphabet = "abc .\\-_ü€\U0001f600\x00\n\"'"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8)))


def random_scalar(rng: random.Random, allow_fallback: bool) -> Any:
    choices: list[Any] = [
        random_text(rng),
        rng.randint(INT64_MIN, UINT64_MAX),
        rng.randint(-1000, 1000),
        rng.uniform(-1e12, 1e12),
        rng.choice([0.0, -0.0, math.inf, -math.inf, math.nan, 5e-324, 1.7976931348623157e308]),
        rng.choice([True, False]),
        None,
    ]
    if allow_fallback:
        choices += [rng.choice([UINT64_MAX + 1, INT64_MIN - 1, 10**40]), "lone \ud800"]
    return rng.choice(choices)


def random_field_value(rng: random.Random, allow_fallback: bool = False, depth: int = 0) -> Any:
    roll = rng.random()
    if depth >= 5 or roll < 0.4:
        return random_scalar(rng, allow_fallback)
    size = rng.randint(0, 5)
    if roll < 0.7:
        return {
            random_text(rng): random_field_value(rng, allow_fallback, depth + 1)
            for _ in range(size)
        }
    return [random_field_value(rng, allow_fallback, depth + 1) for _ in range(size)]


class TestCopyFieldValue:
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("text", id="scalar-str"),
            pytest.param(None, id="scalar-none"),
            pytest.param(-0.0, id="scalar-negative-zero"),
            pytest.param({"a": {}, "b": [], "c": [{}]}, id="empty-containers"),
            pytest.param([True, 1, 1.0, "1", None], id="bool-int-float-not-conflated"),
            pytest.param({"b": 1, "a": 2, "c": 3}, id="key-order"),
            pytest.param({"": 1, "a.b": 2, "a\\.b": 3, "ü": 4, " ": 5}, id="special-keys"),
            pytest.param(
                {"v": [-0.0, math.nan, math.inf, -math.inf, INT64_MIN, UINT64_MAX, 5e-324]},
                id="edge-numbers",
            ),
            pytest.param({"s": ["", "ü€\U0001f600\x00"]}, id="edge-strings"),
            pytest.param({"l": [[1, [2]], {"d": [3]}]}, id="nested-lists"),
            pytest.param(nested(200, "leaf"), id="deep-dict"),
            pytest.param(nested(200, 1, kind=list), id="deep-list"),
        ],
    )
    def test_matches_deepcopy(self, copy_function: Callable[[Any], Any], value: Any) -> None:
        assert_copied_like_deepcopy(copy_function, value)

    @pytest.mark.parametrize("allow_fallback", [False, True], ids=["plain", "with-fallback"])
    def test_random_field_values_match_deepcopy(
        self, copy_function: Callable[[Any], Any], allow_fallback: bool
    ) -> None:
        rng = random.Random(4242)
        for _ in range(500):
            assert_copied_like_deepcopy(copy_function, random_field_value(rng, allow_fallback))

    def test_shared_references_are_copied_separately(
        self, copy_function: Callable[[Any], Any]
    ) -> None:
        shared = [1, 2]
        result = copy_function({"a": shared, "b": shared})
        assert result == {"a": [1, 2], "b": [1, 2]}
        assert result["a"] is not result["b"]


class TestCopyFieldValueFallback:
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param({"n": [UINT64_MAX + 1, INT64_MIN - 1]}, id="ints-beyond-64-bit"),
            pytest.param({"s": "lone \ud800"}, id="lone-surrogate-value"),
            pytest.param({"\udfff": [1]}, id="lone-surrogate-key"),
            pytest.param(2**70, id="top-level-big-int"),
        ],
    )
    def test_unencodable_values_match_deepcopy(
        self, copy_function: Callable[[Any], Any], value: Any
    ) -> None:
        assert_copied_like_deepcopy(copy_function, value)

    def test_nested_unencodable_objects_are_deep_copied(
        self, copy_function: Callable[[Any], Any]
    ) -> None:
        payload = Opaque([1, 2])
        value = {"obj": payload, "plain": [1]}
        result = copy_function(value)
        assert result == value
        assert result["obj"] is not payload and result["obj"].payload is not payload.payload
        assert_independent(result, value)

    @pytest.mark.parametrize(
        "value, expected_path",
        [
            pytest.param("text", "identity", id="scalar"),
            pytest.param({"a": [1]}, "msgspec", id="plain-dict"),
            pytest.param({"n": 2**70}, "recursive", id="big-int"),
            pytest.param({"o": Opaque([1])}, "recursive", id="unencodable-object"),
            pytest.param(collections.OrderedDict(a=1), "msgspec", id="top-level-dict-subclass"),
        ],
    )
    def test_takes_expected_path(self, value: Any, expected_path: str) -> None:
        encoder = mock.Mock(wraps=helper._MSGPACK_ENCODER)
        with (
            mock.patch.object(helper, "_MSGPACK_ENCODER", encoder),
            mock.patch.object(
                helper, "_copy_field_value", wraps=helper._copy_field_value
            ) as recursive,
        ):
            result = copy_field_value(value)
        taken = {
            "msgspec": encoder.encode.called and not recursive.called,
            "recursive": recursive.called,
            "identity": result is value,
        }
        assert [path for path, was_taken in taken.items() if was_taken] == [expected_path]

    def test_cycle_is_copied_like_deepcopy(self) -> None:
        value: dict[str, Any] = {"a": [1]}
        value["self"] = value
        result = copy_field_value(value)
        assert result["self"] is result
        assert result["a"] == [1] and result["a"] is not value["a"]

    def test_cycle_behind_unencodable_object_is_copied_like_deepcopy(self) -> None:
        value: dict[str, Any] = {"obj": Opaque([1])}
        value["self"] = value
        result = copy_field_value(value)
        assert result["self"] is result
        assert result["obj"] == value["obj"] and result["obj"] is not value["obj"]

    def test_excessive_nesting_raises_recursion_error(self) -> None:
        with pytest.raises(RecursionError):
            copy_field_value(nested(100_000, 1))

    def test_unexpected_errors_are_not_swallowed(self) -> None:
        value: JsonObject = {"a": 1}
        encoder = mock.Mock()
        encoder.encode.side_effect = KeyError("boom")
        with mock.patch.object(helper, "_MSGPACK_ENCODER", encoder):
            with pytest.raises(KeyError):
                copy_field_value(value)


class TestCopyFieldValueNonFieldValues:
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param((1, [2]), id="tuple"),
            pytest.param(collections.OrderedDict(a=[1]), id="ordered-dict"),
            pytest.param(Opaque([1]), id="custom-object"),
        ],
    )
    def test_top_level_values_are_converted_like_nested_ones(self, value: Any) -> None:
        """Outside the contract depth does not matter: the top level follows the nested rule."""
        assert_identical(copy_field_value(value), copy_field_value({"v": value})["v"])

    def test_top_level_unencodable_object_is_deep_copied(self) -> None:
        value: Any = Opaque([1])  # deliberately outside the FieldValue contract
        result = copy_field_value(value)
        assert result == value
        assert result is not value and result.payload is not value.payload

    @pytest.mark.parametrize(
        "value, expected",
        [
            pytest.param({"v": (1, 2)}, {"v": [1, 2]}, id="tuple-to-list"),
            pytest.param(
                {"v": datetime.datetime(2026, 1, 1)}, {"v": "2026-01-01T00:00:00"}, id="naive-dt"
            ),
        ],
    )
    def test_msgspec_encodable_types_are_converted(self, value: Any, expected: Any) -> None:
        """Outside the contract types msgspec can encode are converted, not kept."""
        assert_identical(copy_field_value(value), expected)
