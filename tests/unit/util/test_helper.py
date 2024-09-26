# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import re
from unittest import mock

import pytest

from logprep.util.configuration import Configuration
from logprep.util.helper import (
    camel_to_snake,
    get_dotted_field_value,
    get_versions_string,
    pop_dotted_field_value,
    snake_to_camel,
)
from logprep.util.json_handling import is_json
from tests.testdata.metadata import path_to_config


class TestCamelToSnake:
    @pytest.mark.parametrize(
        "camel_case, snake_case",
        [
            ("snakesOnAPlane", "snakes_on_a_plane"),
            ("SnakesOnAPlane", "snakes_on_a_plane"),
            ("snakes_on_a_plane", "snakes_on_a_plane"),
            ("IPhoneHysteria", "i_phone_hysteria"),
            ("iPhoneHysteria", "i_phone_hysteria"),
            ("GeoipEnricher", "geoip_enricher"),
        ],
    )
    def test_camel_to_snake(self, camel_case, snake_case):
        assert camel_to_snake(camel_case) == snake_case


class TestSnakeToCamel:
    @pytest.mark.parametrize(
        "camel_case, snake_case",
        [
            ("SnakesOnAPlane", "snakes_on_a_plane"),
            ("SnakesOnAPlane", "SnakesOnAPlane"),
            ("IPhoneHysteria", "i_phone_hysteria"),
            ("DatetimeExtractor", "datetime_extractor"),
            ("GenericAdder", "generic_adder"),
            ("Dissector", "dissector"),
            ("GeoipEnricher", "geoip_enricher"),
        ],
    )
    def test_snake_to_camel(self, camel_case, snake_case):
        assert snake_to_camel(snake_case) == camel_case


class TestIsJson:
    @pytest.mark.parametrize(
        "data, expected",
        [
            (
                """
                [
                    { "i": "am json"}
                ]
                """,
                True,
            ),
            (
                """
                key1: valid yaml but not json
                key2:
                    - key3: key3
                """,
                False,
            ),
            (
                """
                [
                    "i": "am not valid json but readable as yaml"
                ]
                """,
                False,
            ),
            (
                """
                filter: test_filter
                processor:
                    key1:
                    - key2: value2
                """,
                False,
            ),
        ],
    )
    def test_is_json_returns_expected(self, data, expected):
        with mock.patch("builtins.open", mock.mock_open(read_data=data)):
            assert is_json("mock_path") == expected


class TestGetDottedFieldValue:
    def test_get_dotted_field_value_nesting_depth_zero(self):
        event = {"dotted": "127.0.0.1"}
        dotted_field = "dotted"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "127.0.0.1"

    def test_get_dotted_field_value_nesting_depth_one(self):
        event = {"dotted": {"field": "127.0.0.1"}}
        dotted_field = "dotted.field"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "127.0.0.1"

    def test_get_dotted_field_value_nesting_depth_two(self):
        event = {"some": {"dotted": {"field": "127.0.0.1"}}}
        dotted_field = "some.dotted.field"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "127.0.0.1"

    def test_get_dotted_field_retrieves_sub_dict(self):
        event = {"some": {"dotted": {"field": "127.0.0.1"}}}
        dotted_field = "some.dotted"
        value = get_dotted_field_value(event, dotted_field)
        assert value == {"field": "127.0.0.1"}

    def test_get_dotted_field_retrieves_list(self):
        event = {"some": {"dotted": ["list", "with", "values"]}}
        dotted_field = "some.dotted"
        value = get_dotted_field_value(event, dotted_field)
        assert value == ["list", "with", "values"]

    def test_get_dotted_field_value_that_does_not_exist(self):
        event = {}
        dotted_field = "field"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_value_that_does_not_exist_from_nested_dict(self):
        event = {"some": {}}
        dotted_field = "some.dotted.field"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_value_that_matches_part_of_dotted_field(self):
        event = {"some": "do_not_match"}
        dotted_field = "some.dotted"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_value_key_matches_value(self):
        event = {"get": "dotted"}
        dotted_field = "get.dotted"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_with_list(self):
        event = {"get": ["dotted"]}
        dotted_field = "get.0"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "dotted"

    def test_get_dotted_field_with_nested_list(self):
        event = {"get": ["dotted", ["does_not_matter", "target"]]}
        dotted_field = "get.1.1"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "target"

    def test_get_dotted_field_with_list_not_found(self):
        event = {"get": ["dotted"]}
        dotted_field = "get.0.1"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_with_list_last_element(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.-1"
        value = get_dotted_field_value(event, dotted_field)
        assert value == "target"

    def test_get_dotted_field_with_out_of_bounds_index(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.3"
        value = get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_fields_with_list_slicing(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.0:2"
        value = get_dotted_field_value(event, dotted_field)
        assert value == ["dotted", "does_not_matter"]

    def test_get_dotted_fields_with_list_slicing_short(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.:2"
        value = get_dotted_field_value(event, dotted_field)
        assert value == ["dotted", "does_not_matter"]

    def test_get_dotted_fields_reverse_order_with_slicing(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.::-1"
        value = get_dotted_field_value(event, dotted_field)
        assert value == ["target", "does_not_matter", "dotted"]

    def test_get_dotted_fiels_with_list_slicing_2(self):
        event = {"get": ["dotted", "does_not_matter", "target"]}
        dotted_field = "get.::2"
        value = get_dotted_field_value(event, dotted_field)
        assert value == ["dotted", "target"]


class TestPopDottedFieldValue:
    def test_get_dotted_field_removes_source_field_in_nested_structure_but_leaves_sibling(self):
        event = {"get": {"nested": "field", "other": "field"}}
        dotted_field = "get.nested"
        value = pop_dotted_field_value(event, dotted_field)
        assert value == "field"
        assert event == {"get": {"other": "field"}}

    def test_get_dotted_field_removes_source_field(self):
        event = {"get": {"nested": "field"}}
        dotted_field = "get.nested"
        value = pop_dotted_field_value(event, dotted_field)
        assert value == "field"
        assert not event

    def test_get_dotted_field_removes_source_field2(self):
        event = {"get": {"very": {"deeply": {"nested": {"field": "value"}}}}}
        dotted_field = "get.very.deeply.nested"
        value = pop_dotted_field_value(event, dotted_field)
        assert value == {"field": "value"}
        assert not event


class TestGetVersionString:
    def test_get_version_string(self):
        config = Configuration()
        config.version = "0.1.0"
        expected_pattern = (
            r"python version:\s+3\.\d+\.\d+\n"
            r"logprep version:\s+[^\s]+\n"
            r"configuration version:\s+0\.1\.0, None"
        )

        result = get_versions_string(config)
        assert re.search(expected_pattern, result)

    def test_get_version_string_with_config_source(self):
        config = Configuration.from_sources([path_to_config])
        expected_pattern = (
            r"python version:\s+3\.\d+\.\d+\n"
            r"logprep version:\s+[^\s]+\n"
            r"configuration version:\s+1,\s+file://[^\s]+/config\.yml"
        )

        result = get_versions_string(config)
        assert re.search(expected_pattern, result)

    def test_get_version_string_with_multiple_config_sources(self):
        config = Configuration.from_sources([path_to_config, path_to_config])
        expected_pattern = (
            r"python version:\s+3\.\d+\.\d+\n"
            r"logprep version:\s+[^\s]+\n"
            r"configuration version:\s+1,\s1,\s+file://[^\s]+/config\.yml,\s+file://[^\s]+/config\.yml"
        )

        result = get_versions_string(config)
        assert re.search(expected_pattern, result)

    def test_get_version_string_without_config(self):
        expected_pattern = (
            r"python version:\s+3\.\d+\.\d+\n"
            r"logprep version:\s+[^\s]+\n"
            r"configuration version:\s+no configuration found in file:///etc/logprep/pipeline.yml"
        )

        result = get_versions_string(None)
        assert re.search(expected_pattern, result)
