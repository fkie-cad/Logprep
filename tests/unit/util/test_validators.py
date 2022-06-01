# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from unittest import mock

import pytest

from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.util.validators import (
    json_validator,
    file_validator,
    list_of_dirs_validator,
    list_of_files_validator,
    url_validator,
    list_of_urls_validator,
    directory_validator,
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
