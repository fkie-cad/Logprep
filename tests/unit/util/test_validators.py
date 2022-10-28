# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from typing import Optional
from unittest import mock

import pytest
from attr import define, field
from attrs import validators

from logprep.factory_error import InvalidConfigurationError
from logprep.util.validators import (
    json_validator,
    file_validator,
    list_of_dirs_validator,
    list_of_files_validator,
    one_of_validator,
    url_validator,
    list_of_urls_validator,
    directory_validator,
    dict_structure_validator,
    min_len_validator,
)


class TestJsonValidator:
    @pytest.mark.parametrize(
        "file_data, raises",
        [
            ('{"i": "am valid"}', False),
            ("i am not json", True),
            ("{'i': 'am not valid json'}", True),
            ('{"i": ["am", "not", "valid", "json",]}', True),
        ],
    )
    def test_raises_if_not_valid_json(self, file_data, raises):
        mock_open = mock.mock_open(read_data=file_data)
        with mock.patch("builtins.open", mock_open):
            if raises:
                with pytest.raises(InvalidConfigurationError, match=r"is not valid json"):
                    json_validator(None, "does_not_matter", "/mock/file/path")
            else:
                json_validator(None, "does_not_matter", "/mock/file/path")


class TestFileValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not file_validator(None, attribute(), None)

    def test_raises_if_path_is_no_string(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a str"):
            file_validator(None, attribute(), 8472)

    def test_raises_if_file_does_not_exist(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                file_validator(None, attribute(), "i/do/not/exist")

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isfile", return_value=False)
    def test_raises_if_path_is_no_file(self, _, __):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a file"):
            file_validator(None, attribute(), "i/am/no.file")


class TestDirValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not directory_validator(None, attribute(), None)

    def test_raises_if_dir_is_no_string(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a str"):
            directory_validator(None, attribute(), 8472)

    def test_raises_if_file_does_not_exist(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                directory_validator(None, attribute(), "i/do/not/exist")

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isfile", return_value=False)
    def test_raises_if_path_is_no_file(self, _, __):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a directory"):
            directory_validator(None, attribute(), "i/am/not/a.directory")


class TestURLValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not url_validator(None, attribute(), None)

    def test_raises_if_url_is_no_string(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a str"):
            url_validator(None, attribute(), 8472)

    def test_raises_if_no_schema_netloc_and_path_is_given(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(
            InvalidConfigurationError, match=r"has no schema, net location and path"
        ):
            url_validator(None, attribute(), "?param=1#fragment1")

    def test_raises_if_file_of_plain_file_path_does_not_exist(self):
        """Proxy test for file_validator, file_validator has its own tests"""
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            url_validator(None, attribute(), "i/do/not/exist")

    def test_raises_if_url_file_schema_is_malformed(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"has malformed file location"):
            with mock.patch("os.path.exists", return_value=False):
                url_validator(
                    None, attribute(), "file://malformed/file/path?because=of&params=and#fragments"
                )

    def test_raises_if_file_does_not_exists_of_well_formed_file_path(self):
        """Proxy test for file_validator, file_validator has its own tests"""
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                url_validator(None, attribute(), "file://i/do/not/exist")


class TestListOfDirsValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not list_of_dirs_validator(None, attribute(), None)

    def test_raises_if_list_of_dirs_is_no_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a list"):
            list_of_dirs_validator(None, attribute(), "no list")

    def test_raises_if_list_of_dirs_is_empty_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is empty list"):
            list_of_dirs_validator(None, attribute(), [])

    def test_raises_if_element_in_list_does_not_exist(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                list_of_dirs_validator(None, attribute(), ["i/do/not/exist"])

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isdir", return_value=False)
    def test_raises_if_element_in_list_is_not_a_directory(self, _, __):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a directory"):
            list_of_dirs_validator(None, attribute(), ["i/am/no.directory"])


class TestListOfFilesValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not list_of_files_validator(None, attribute(), None)

    def test_raises_if_list_of_files_is_no_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a list"):
            list_of_files_validator(None, attribute(), "no.list")

    def test_raises_if_list_of_files_is_empty_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is empty list"):
            list_of_files_validator(None, attribute(), [])

    def test_raises_if_element_in_list_does_not_exist(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                list_of_files_validator(None, attribute(), ["i/do/not/exist"])

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isdir", return_value=False)
    def test_raises_if_element_in_list_is_not_a_file(self, _, __):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a file"):
            list_of_files_validator(None, attribute(), ["i/am/no.file"])


class TestListOfUrlsValidator:
    def test_validator_passes_on_not_set_optional_attribute(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        assert not list_of_urls_validator(None, attribute(), None)

    def test_raises_if_url_list_is_no_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is not a list"):
            list_of_urls_validator(None, attribute(), "no.list")

    def test_raises_if_url_list_is_empty_list(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"is empty list"):
            list_of_urls_validator(None, attribute(), [])

    def test_raises_if_element_in_list_does_not_exist(self):
        """Proxy test for url_validator, url_validator has its own tests"""
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(InvalidConfigurationError, match=r"does not exist"):
            with mock.patch("os.path.exists", return_value=False):
                list_of_urls_validator(None, attribute(), ["i/do/not/exist"])


class TestDictStructureValidator:
    def test_raises_on_type_missmatch_in_non_optional_case(self):
        value = {
            "some_option": "with string value",
        }
        reference_dict = {
            "some_option": int,
        }
        with pytest.raises(
            InvalidConfigurationError,
            match=r"some_option' has wrong type <class 'str'>, expected <class 'int'>.",
        ):
            dict_structure_validator(None, None, value, reference_dict)

    def test_raises_on_type_missmatch_in_optional_case(self):
        value = {
            "some_option": "with string value",
        }
        reference_dict = {
            "some_option": Optional[int],
        }
        with pytest.raises(
            InvalidConfigurationError,
            match=r"'some_option' has wrong type <class 'str'>, expected [typing\.Optional\[int\]|typing\.Union\[int, NoneType\]].",
        ):
            dict_structure_validator(None, None, value, reference_dict)

    def test_raises_on_missing_option(self):
        value = {
            "some_option": "with string value",
        }
        reference_dict = {"some_option": str, "other_expected_option": str}
        with pytest.raises(
            InvalidConfigurationError,
            match=r"following key is missing: 'other_expected_option'",
        ):
            dict_structure_validator(None, None, value, reference_dict)

    def test_does_not_raise_on_missing_optional_option(self):
        value = {
            "some_option": "with string value",
        }
        reference_dict = {"some_option": str, "other_optional_option": Optional[str]}
        dict_structure_validator(None, None, value, reference_dict)

    def test_raises_on_unknown_option(self):
        value = {"some_option": "with string value", "something": "unknown"}
        reference_dict = {
            "some_option": str,
        }
        with pytest.raises(
            InvalidConfigurationError, match=r"following keys are unknown: \{'something'\}"
        ):
            dict_structure_validator(None, None, value, reference_dict)

    def test_raises_on_validation_of_nested_non_optional_config_object(self):
        @define(kw_only=True)
        class SomeNestedOptionClass:
            expected_str_sub_field: str = field(validator=validators.instance_of(str))

        value = {
            "some_option": "with string value",
            "sub_options": {"expected_str_sub_field": 12},  # should be string
        }
        reference_dict = {"some_option": str, "sub_options": SomeNestedOptionClass}
        with pytest.raises(TypeError, match=r"expected_str_sub_field' must be <class 'str'>"):
            dict_structure_validator(None, None, value, reference_dict)

    def test_raises_on_validation_of_nested_optional_config_object(self):
        @define(kw_only=True)
        class SomeNestedOptionClass:
            expected_str_sub_field: str = field(validator=validators.instance_of(str))

        value = {
            "some_option": "with string value",
            "sub_options": {
                "expected_str_sub_field": 12,  # should be string
            },
        }
        reference_dict = {"some_option": str, "sub_options": Optional[SomeNestedOptionClass]}
        with pytest.raises(TypeError, match=r"expected_str_sub_field' must be <class 'str'>"):
            dict_structure_validator(None, None, value, reference_dict)

    def test_does_not_raise_on_validation_of_nested_config_object(self):
        @define(kw_only=True)
        class SomeNestedOptionClass:
            expected_str_sub_field: str = field(validator=validators.instance_of(str))

        value = {
            "some_option": "with string value",
            "sub_options": {
                "expected_str_sub_field": "i am really a str",
            },
        }
        reference_dict = {"some_option": str, "sub_options": SomeNestedOptionClass}
        dict_structure_validator(None, None, value, reference_dict)

    def test_does_not_raise_on_validation_of_nested_optional_config_object(self):
        @define(kw_only=True)
        class SomeNestedOptionClass:
            expected_str_sub_field: str = field(validator=validators.instance_of(str))

        value = {
            "some_option": "with string value",
            "sub_options": {
                "expected_str_sub_field": "i am really a str",
            },
        }
        reference_dict = {"some_option": str, "sub_options": Optional[SomeNestedOptionClass]}
        dict_structure_validator(None, None, value, reference_dict)

    def test_does_not_raise_on_validation_of_nested_optional_config_object_while_optional_is_missing(
        self,
    ):
        @define(kw_only=True)
        class SomeNestedOptionClass:
            expected_str_sub_field: str = field(validator=validators.instance_of(str))

        value = {
            "some_option": "with string value",
        }
        reference_dict = {"some_option": str, "sub_options": Optional[SomeNestedOptionClass]}
        dict_structure_validator(None, None, value, reference_dict)


class TestMinLenValidator:
    def test_does_not_raise_if_len_is_equal_than_expected_length(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        min_len_validator(None, attribute(), ["first", "second"], min_length=2)

    def test_does_not_raise_if_len_is_bigger_than_expected_length(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        min_len_validator(None, attribute(), ["first", "second", "third"], min_length=2)

    def test_raises_if_len_is_smaller_than_expected(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        with pytest.raises(ValueError, match=r"Length of 'testname' must be => 2: 1"):
            min_len_validator(None, attribute(), ["only one element"], min_length=2)


class TestOneOfValidator:
    def test_member_list_item_is_a_dict_key(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        value = {"item1": "does not matter"}
        member_list = ["item1", "item2"]
        one_of_validator(None, attribute, value, member_list)

    def test_member_list_item_is_a_list_member(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        value = ["item1", "does not matter"]
        member_list = ["item1", "item2"]
        one_of_validator(None, attribute, value, member_list)

    def test_member_list_item_is_not_a_dict_key(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        value = {"item1": "does not matter"}
        member_list = ["item2", "item3"]
        with pytest.raises(
            ValueError, match=r"testname has to contain one of these members \['item2', 'item3'\]"
        ):
            one_of_validator(None, attribute, value, member_list)

    def test_member_list_item_is_not_a_list_member(self):
        attribute = type("myclass", (), {"name": "testname", "default": None})
        value = ["item1", "does not matter"]
        member_list = ["item2", "item3"]
        with pytest.raises(
            ValueError, match=r"testname has to contain one of these members \['item2', 'item3'\]"
        ):
            one_of_validator(None, attribute, value, member_list)
