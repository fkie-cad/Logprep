# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.constructor import ConstructorError

from logprep.util.tag_yaml_loader import init_yaml_loader_tags


@pytest.fixture(name="yaml_dict_file_path")
def fixture_yaml_dict_file_path(tmp_path) -> str:
    some_dict_yml = """
            .*foo.*: foo
            bar. *: bar
            .*baz: baz
            """
    return write_yaml_file_into_directory(some_dict_yml, tmp_path)


@pytest.fixture(name="empty_yaml_file_path")
def fixture_empty_yaml_file_path(tmp_path) -> str:
    return write_yaml_file_into_directory("", tmp_path)


@pytest.fixture(name="yaml_file_with_valid_include_tag")
def fixture_yaml_file_with_valid_include_tag(yaml_dict_file_path, tmp_path) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {yaml_dict_file_path}
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_invalid_include_tag")
def fixture_yaml_file_with_invalid_include_tag(tmp_path) -> str:
    yml_with_tag = """
    filter: 'something'
    processor:
        some_dict: !include
            - foo
            - bar
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_include_tag_no_file")
def fixture_yaml_file_with_include_tag_no_file(yaml_dict_file_path, tmp_path) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {yaml_dict_file_path}_i_do_not_exist.yml
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_include_tag_empty_file")
def fixture_yaml_file_with_include_tag_empty_file(empty_yaml_file_path, tmp_path) -> str:
    yml_with_tag = f"""
    filter: 'something'
    processor:
        some_dict: !include {empty_yaml_file_path}
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_valid_list_anchor_tag")
def fixture_yaml_file_with_valid_list_anchor_tag(tmp_path) -> str:
    yml_with_tag = """
    filter: 'something'
    processor:
        some_node: !set_anchor
            - a
            - b
        another_node: !load_anchor
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_valid_dict_anchor_tag")
def fixture_yaml_file_with_valid_dict_anchor_tag(tmp_path) -> str:
    yml_with_tag = """
filter: 'something'
processor:
    some_node: !set_anchor:0
        foo: 1
        bar: 2
        baz: 3
    another_node: !load_anchor:0
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_file_with_nested_valid_dict_anchor_tag")
def fixture_yaml_file_with_nested_valid_dict_anchor_tag(tmp_path) -> str:
    yml_with_tag = """
filter: 'something'
processor:
    some_node: !set_anchor:0
        foo:
            bar: 2
            baz: 3
    another_node: !load_anchor:0
    """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_valid_anchor_tag_in_two_documents")
def fixture_yaml_valid_anchor_tag_in_two_documents(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !set_anchor
                - a
                - b
---
        processor:
            another_node: !load_anchor
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_scalar_anchor_tag_in_two_documents")
def fixture_yaml_scalar_anchor_tag_in_two_documents(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !set_anchor some value
---
        processor:
            another_node: !load_anchor
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_scalar_anchor_tag_new_line")
def fixture_yaml_scalar_anchor_tag_new_line(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !set_anchor
              some value
---
        processor:
            another_node: !load_anchor
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_empty_scalar_anchor_tag")
def fixture_yaml_empty_scalar_anchor_tag(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !set_anchor
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_set_anchor")
def fixture_yaml_set_anchor(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !set_anchor
                - a
                - b
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_load_anchor")
def fixture_yaml_load_anchor(tmp_path) -> str:
    yml_with_tag = """
        processor:
            some_node: !load_anchor
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_multiple_anchor_tags")
def fixture_yaml_multiple_anchor_tags(tmp_path) -> str:
    yml_with_tag = """
        processor:
            node_0: !set_anchor:0
                value_0
            node_1: !set_anchor:1
                value_1
---
        processor:
            node_0: !load_anchor:0
            node_1: !load_anchor:1
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_invalid_anchor_tag_name")
def fixture_yaml_invalid_anchor_tag_name(tmp_path) -> str:
    yml_with_tag = """
        processor:
            node_0: !set_anchor:0
                value_0
            node_1: !set_anchor:10
                value_1
---
        processor:
            node_0: !load_anchor:0
            node_1: !load_anchor:10
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_anchor_tag_name_zero_and_none_equal")
def fixture_yaml_anchor_tag_name_zero_and_none_equal(tmp_path) -> str:
    yml_with_tag = """
        processor:
            node_0: !set_anchor value_0
---
        processor:
            node_0: !load_anchor:0
---
        processor:
            node_1: !set_anchor:0 value_1
---
        processor:
            node_1: !load_anchor value_1
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_nested_empty_anchor_tag")
def fixture_yaml_nested_empty_anchor_tag(tmp_path) -> str:
    yml_with_tag = """
        processor:
            node_0: !set_anchor
                node_1: !set_anchor:1
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


@pytest.fixture(name="yaml_nested_include_tag")
def fixture_yaml_nested_include_tag(yaml_dict_file_path, tmp_path) -> str:
    yml_with_tag = f"""
        processor:
            node_0: !set_anchor
                node_1: !include {yaml_dict_file_path}
        """
    return write_yaml_file_into_directory(yml_with_tag, tmp_path)


def write_yaml_file_into_directory(file_content: str, target_directory: Path):
    rule_file = tempfile.mktemp(dir=target_directory, suffix=".yml")
    with open(rule_file, "w", encoding="utf-8") as file:
        file.write(file_content)
    return rule_file


class TestTagYamlLoader:
    def test_load_tag_from_valid_file_for_given_loader_type(self, yaml_file_with_valid_include_tag):
        yaml = YAML(pure=True, typ="safe")
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

    def test_load_with_list_anchor_tag(self, yaml_file_with_valid_list_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_yaml(yaml_file_with_valid_list_anchor_tag, yaml)
        assert loaded["processor"]["another_node"] == ["a", "b"]

    def test_load_with_dict_anchor_tag(self, yaml_file_with_valid_dict_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_yaml(yaml_file_with_valid_dict_anchor_tag, yaml)
        assert loaded["processor"]["another_node"] == {"foo": 1, "bar": 2, "baz": 3}

    def test_load_with_nested_dict_anchor_tag(self, yaml_file_with_nested_valid_dict_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_yaml(yaml_file_with_nested_valid_dict_anchor_tag, yaml)
        assert loaded["processor"]["another_node"] == {"foo": {"bar": 2, "baz": 3}}

    def test_load_with_anchor_tag_with_two_documents(self, yaml_valid_anchor_tag_in_two_documents):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_valid_anchor_tag_in_two_documents, yaml)
        assert loaded[0]["processor"]["some_node"] == ["a", "b"]
        assert loaded[1]["processor"]["another_node"] == ["a", "b"]

    def test_load_with_scalar_anchor_tag_with_two_documents(
        self, yaml_scalar_anchor_tag_in_two_documents
    ):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_scalar_anchor_tag_in_two_documents, yaml)
        assert loaded[0]["processor"]["some_node"] == "some value"
        assert loaded[1]["processor"]["another_node"] == "some value"

    def test_load_with_scalar_anchor_tag_with_new_line(self, yaml_scalar_anchor_tag_new_line):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_scalar_anchor_tag_new_line, yaml)
        assert loaded[0]["processor"]["some_node"] == "some value"
        assert loaded[1]["processor"]["another_node"] == "some value"

    def test_load_with_empty_scalar_anchor_tag(self, yaml_empty_scalar_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(ValueError, match=r"empty anchor"):
            self._load_all_yaml(yaml_empty_scalar_anchor_tag, yaml)

    def test_load_does_not_exist(self, yaml_load_anchor):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")

        with pytest.raises(
            ValueError, match=r"Global anchor '0' is not defined within this YAML stream"
        ):
            self._load_yaml(yaml_load_anchor, yaml)

    def test_load_with_anchor_tag_with_two_separate_documents(
        self, yaml_set_anchor, yaml_load_anchor
    ):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_set_anchor, yaml)
        assert loaded[0]["processor"]["some_node"] == ["a", "b"]
        loaded = self._load_all_yaml(yaml_load_anchor, yaml)
        assert loaded[0]["processor"]["some_node"] == ["a", "b"]

    def test_with_yaml_multiple_anchor_tags(self, yaml_multiple_anchor_tags):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_multiple_anchor_tags, yaml)
        assert loaded[0]["processor"]["node_0"] == "value_0"
        assert loaded[1]["processor"]["node_1"] == "value_1"

    def test_with_invalid_yaml_anchor_tag_name(self, yaml_invalid_anchor_tag_name):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(ConstructorError, match=r"tag '!set_anchor:10'"):
            self._load_all_yaml(yaml_invalid_anchor_tag_name, yaml)

    def test_anchor_tag_name_zero_and_none_equal(self, yaml_anchor_tag_name_zero_and_none_equal):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        loaded = self._load_all_yaml(yaml_anchor_tag_name_zero_and_none_equal, yaml)
        assert loaded[0]["processor"]["node_0"] == "value_0"
        assert loaded[3]["processor"]["node_1"] == "value_1"

    def test_with_nested_anchor_tag(self, yaml_nested_empty_anchor_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        with pytest.raises(ValueError, match=r"empty anchor"):
            self._load_all_yaml(yaml_nested_empty_anchor_tag, yaml)

    def test_with_nested_include_tag(self, yaml_nested_include_tag):
        yaml = YAML(pure=True, typ="safe")
        init_yaml_loader_tags("safe")
        assert self._load_all_yaml(yaml_nested_include_tag, yaml) == [
            {
                "processor": {
                    "node_0": {
                        "node_1": {
                            ".*baz": "baz",
                            ".*foo.*": "foo",
                            "bar. *": "bar",
                        },
                    },
                },
            },
        ]

    @staticmethod
    def _load_yaml(yaml_file, yaml):
        with open(yaml_file, "r", encoding="utf-8") as file:
            return yaml.load(file)

    @staticmethod
    def _load_all_yaml(yaml_file, yaml):
        with open(yaml_file, "r", encoding="utf-8") as file:
            return list(yaml.load_all(file))
