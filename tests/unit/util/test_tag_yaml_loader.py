# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import tempfile

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.constructor import ConstructorError

from logprep.util.tag_yaml_loader import init_yaml_loader_tags


@pytest.fixture(name="yaml_directory")
def fixture_yaml_directory() -> str:
    return tempfile.mkdtemp()


@pytest.fixture(name="yaml_dict_file_path")
def fixture_yaml_dict_file_path(yaml_directory) -> str:
    some_dict_yml = """
            .*foo.*: foo
            bar. *: bar
            .*baz: baz
            """
    return write_yaml_file_into_directory(some_dict_yml, yaml_directory)


@pytest.fixture(name="empty_yaml_file_path")
def fixture_empty_yaml_file_path(yaml_directory) -> str:
    return write_yaml_file_into_directory("", yaml_directory)


@pytest.fixture(name="yaml_file_with_valid_include_tag")
def fixture_yaml_file_with_valid_include_tag(yaml_dict_file_path, yaml_directory) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {yaml_dict_file_path}
    """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_file_with_invalid_include_tag")
def fixture_yaml_file_with_invalid_include_tag(yaml_dict_file_path, yaml_directory) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include
            - foo
            - bar
    """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_file_with_include_tag_no_file")
def fixture_yaml_file_with_include_tag_no_file(yaml_dict_file_path, yaml_directory) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {yaml_dict_file_path}_i_do_not_exist.yml
    """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_file_with_include_tag_empty_file")
def fixture_yaml_file_with_include_tag_empty_file(empty_yaml_file_path, yaml_directory) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {empty_yaml_file_path}
    """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_file_with_valid_anchor_tag")
def fixture_yaml_file_with_valid_anchor_tag(yaml_directory) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_node: !set_anchor foo
            - a
            - b
        another_node: !load_anchor foo
    """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_valid_anchor_tag_in_two_documents")
def fixture_yaml_valid_anchor_tag_in_two_documents(yaml_directory) -> str:
    yml_with_tag = f"""
        processor:
            some_node: !set_anchor foo
                - a
                - b
---
        processor:
            another_node: !load_anchor foo
        """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_scalar_anchor_tag_in_two_documents")
def fixture_yaml_scalar_anchor_tag_in_two_documents(yaml_directory) -> str:
    yml_with_tag = f"""
        processor:
            some_node: !set_anchor foo some value
---
        processor:
            another_node: !load_anchor foo
        """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_empty_scalar_anchor_tag")
def fixture_yaml_empty_scalar_anchor_tag(yaml_directory) -> str:
    yml_with_tag = f"""
        processor:
            some_node: !set_anchor foo
        """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_set_anchor")
def fixture_yaml_set_anchor(yaml_directory) -> str:
    yml_with_tag = f"""
        processor:
            some_node: !set_anchor foo
                - a
                - b
        """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


@pytest.fixture(name="yaml_load_anchor")
def fixture_yaml_load_anchor(yaml_directory) -> str:
    yml_with_tag = f"""
        processor:
            some_node: !load_anchor foo
        """
    return write_yaml_file_into_directory(yml_with_tag, yaml_directory)


def write_yaml_file_into_directory(file_content: str, target_directory: str):
    rule_file = tempfile.mktemp(dir=target_directory, suffix=".yml")
    with open(rule_file, "w", encoding="utf-8") as file:
        file.write(file_content)
    return rule_file


class TestTagYamlLoader:
    def test_load_tag_from_valid_file_for_given_loader_type(self, yaml_file_with_valid_include_tag):
        yaml = YAML(pure=True, typ="safe")

        with pytest.raises(ConstructorError, match=r"!include"):
            self._load_yaml(yaml_file_with_valid_include_tag, yaml)

        init_yaml_loader_tags("safe")
        loaded = self._load_yaml(yaml_file_with_valid_include_tag, yaml)

        expected = {".*foo.*": "foo", "bar. *": "bar", ".*baz": "baz"}
        assert loaded["processor"]["some_dict"] == expected

    def test_load_tag_from_valid_file_with_load_all(self, yaml_file_with_valid_include_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")

        loaded = self._load_all_yaml(yaml_file_with_valid_include_tag, yaml)
        loaded = list(loaded)

        expected = {".*foo.*": "foo", "bar. *": "bar", ".*baz": "baz"}
        assert loaded[0]["processor"]["some_dict"] == expected

    def test_load_with_invalid_include_tag(self, yaml_file_with_invalid_include_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(ValueError, match=r"not a file path"):
            self._load_yaml(yaml_file_with_invalid_include_tag, yaml)

    def test_load_with_include_tag_to_non_existent_file(self, yaml_file_with_include_tag_no_file):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(FileNotFoundError, match=r"_i_do_not_exist.yml"):
            self._load_yaml(yaml_file_with_include_tag_no_file, yaml)

    def test_load_with_include_tag_to_empty_file(self, yaml_file_with_include_tag_empty_file):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(ValueError, match=r"is empty"):
            self._load_yaml(yaml_file_with_include_tag_empty_file, yaml)

    def test_load_with_anchor_tag(self, yaml_file_with_valid_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_yaml(yaml_file_with_valid_anchor_tag, yaml)
        assert loaded["processor"]["another_node"] == ["a", "b"]

    def test_load_with_anchor_tag_with_two_documents(self, yaml_valid_anchor_tag_in_two_documents):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_valid_anchor_tag_in_two_documents, yaml)
        loaded = list(loaded)
        assert loaded[0]["processor"]["some_node"] == ["a", "b"]
        assert loaded[1]["processor"]["another_node"] == ["a", "b"]

    def test_load_with_scalar_anchor_tag_with_two_documents(
        self, yaml_scalar_anchor_tag_in_two_documents
    ):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_scalar_anchor_tag_in_two_documents, yaml)
        loaded = list(loaded)
        assert loaded[0]["processor"]["some_node"] == "some value"
        assert loaded[1]["processor"]["another_node"] == "some value"

    def test_load_with_empty_scalar_anchor_tag(
            self, yaml_empty_scalar_anchor_tag
    ):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_empty_scalar_anchor_tag, yaml)
        with pytest.raises(ValueError, match=r"empty scalar anchor"):
            list(loaded)

    def test_load_does_not_exist(self, yaml_set_anchor, yaml_load_anchor):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")

        with pytest.raises(ValueError, match=r"not a defined anchor"):
            self._load_yaml(yaml_load_anchor, yaml)

    def test_load_with_anchor_tag_with_two_separate_documents(
        self, yaml_set_anchor, yaml_load_anchor
    ):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = list(self._load_all_yaml(yaml_set_anchor, yaml))
        assert loaded[0]["processor"]["some_node"] == ["a", "b"]

        with pytest.raises(ValueError, match=r"not a defined anchor"):
            list(self._load_all_yaml(yaml_load_anchor, yaml))

    @staticmethod
    def _load_yaml(yaml_file, yaml):
        with open(yaml_file, "r", encoding="utf-8") as file:
            return yaml.load(file)

    @staticmethod
    def _load_all_yaml(yaml_file, yaml):
        with open(yaml_file, "r", encoding="utf-8") as file:
            return yaml.load_all(file.read())
