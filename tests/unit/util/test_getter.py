# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import os
from pathlib import Path
from unittest import mock

import pytest
import responses
from requests.auth import HTTPBasicAuth
from requests.exceptions import Timeout
from ruamel.yaml import YAML

from logprep._version import get_versions
from logprep.util.getter import FileGetter, GetterFactory, GetterNotFoundError, HttpGetter

yaml = YAML(pure=True, typ="safe")


class TestGetterFactory:
    def test_raises_if_getter_not_implemeted(self):
        with pytest.raises(GetterNotFoundError):
            GetterFactory.from_string("not_exist://my/file")

    @pytest.mark.parametrize(
        "target_string, expected_protocol, expected_target",
        [
            ("file://my/file", "file", "my/file"),
            ("file:///my/file", "file", "/my/file"),
            ("/my/file", "file", "/my/file"),
            ("my/file", "file", "my/file"),
            ("http://my/file", "http", "my/file"),
            ("https://my/file", "https", "my/file"),
            ("http://user:password@my/file", "http", "my/file"),
            ("https://user:password@my/file", "https", "my/file"),
            ("http://oauth:ajpf0q9vrfásdjlk__234d@my/file", "http", "my/file"),
            ("https://oauth:ajpf0q9vrfásdjlk__234d@my/file", "https", "my/file"),
        ],
    )
    def test_from_string_sets_protocol_and_target(
        self, target_string, expected_protocol, expected_target
    ):
        my_getter = GetterFactory.from_string(target_string)
        assert my_getter.protocol == expected_protocol
        assert my_getter.target == expected_target

    def test_getter_expands_from_environment(self):
        os.environ["PYTEST_TEST_TOKEN"] = "mytesttoken"
        os.environ["PYTEST_TEST_TARGET"] = "the-web-target"
        url = "https://oauth:${PYTEST_TEST_TOKEN}@${PYTEST_TEST_TARGET}"
        my_getter = GetterFactory.from_string(url)
        assert my_getter._username == "oauth"
        assert my_getter._password == "mytesttoken"
        assert my_getter.target == "the-web-target"

    def test_getter_expands_not_set_environment_to_blank(self):
        if "PYTEST_TEST_TOKEN" in os.environ:
            os.environ.pop("PYTEST_TEST_TOKEN")
        if "PYTEST_TEST_TARGET" in os.environ:
            os.environ.pop("PYTEST_TEST_TARGET")
        url = "https://oauth:${PYTEST_TEST_TOKEN}@randomtarget/${PYTEST_TEST_TARGET}"
        my_getter = GetterFactory.from_string(url)
        assert my_getter._password is None
        assert my_getter.target == "oauth:@randomtarget/"

    def test_getter_expands_environment_variables_in_content(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken"

    def test_getter_expands_environment_variables_in_yaml_content(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text(
            """---
key: $PYTEST_TEST_TOKEN
list:
    - first element
    - $PYTEST_TEST_TOKEN
    - ${PYTEST_TEST_TOKEN}-with-additional-string
dict: {key: value, second_key: $PYTEST_TEST_TOKEN}
"""
        )
        my_getter = GetterFactory.from_string(str(testfile))
        expected = {
            "key": "mytoken",
            "list": ["first element", "mytoken", "mytoken-with-additional-string"],
            "dict": {"key": "value", "second_key": "mytoken"},
        }
        assert my_getter.get_yaml() == expected


class TestFileGetter:
    def test_factory_returns_file_getter_without_protocol(self):
        file_getter = GetterFactory.from_string("/my/file")
        assert isinstance(file_getter, FileGetter)

    def test_factory_returns_file_getter_with_protocol(self):
        file_getter = GetterFactory.from_string("file:///my/file")
        assert isinstance(file_getter, FileGetter)

    def test_get_returns_content(self):
        file_getter = GetterFactory.from_string("/my/file")
        with mock.patch("pathlib.Path.open", mock.mock_open(read_data=b"my content")) as mock_open:
            content = file_getter.get()
            assert content == "my content"

    def test_get_returns_binary_content(self):
        file_getter = GetterFactory.from_string("/my/file")
        with mock.patch("pathlib.Path.open", mock.mock_open(read_data=b"my content")) as mock_open:
            content = file_getter.get_raw()
            mock_open.assert_called_with(mode="rb")
            assert content == b"my content"

    @pytest.mark.parametrize(
        "method_name, input_content, expected_output",
        [
            (
                "get_yaml",
                b"""---
first_dict:
    key:
        - valid_list_element
        - valid_list_element
                """,
                {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
            ),
            (
                "get_yaml",
                b"""---
first_dict:
    key:
        - valid_list_element
        - valid_list_element
---
second_dict:
    key:
        - valid_list_element
        - valid_list_element
                """,
                [
                    {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                    {"second_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                ],
            ),
            (
                "get_json",
                b"""{
                    "first_dict": {
                        "key": [
                            "valid_list_element",
                            "valid_list_element"
                        ]
                    }
                }
                """,
                {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
            ),
            (
                "get_json",
                b"""{
                    "first_dict": {
                        "key": [
                            "valid_list_element",
                            "valid_list_element"
                        ]
                    }
                }
                """,
                {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
            ),
            (
                "get_json",
                b"""[{
                    "first_dict": {
                        "key": [
                            "valid_list_element",
                            "valid_list_element"
                        ]
                    }
                },
                {
                    "second_dict": {
                        "key": [
                            "valid_list_element",
                            "valid_list_element"
                        ]
                    }
                }]
                """,
                [
                    {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                    {"second_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                ],
            ),
            (
                "get_jsonl",
                b"""{"first_dict": {"key": ["valid_list_element","valid_list_element"]}}
                {"second_dict": {"key": ["valid_list_element","valid_list_element"]}}
                """,
                [
                    {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                    {"second_dict": {"key": ["valid_list_element", "valid_list_element"]}},
                ],
            ),
        ],
    )
    def test_parses_content(self, method_name, input_content, expected_output):
        file_getter = GetterFactory.from_string("/my/file")
        method = getattr(file_getter, method_name)
        with mock.patch("pathlib.Path.open", mock.mock_open(read_data=input_content)):
            output = method()
            assert output == expected_output


class TestHttpGetter:
    def test_factory_returns_http_getter_for_http(self):
        http_getter = GetterFactory.from_string("http://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    def test_factory_returns_http_getter_for_https(self):
        http_getter = GetterFactory.from_string("https://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    @responses.activate
    def test_get_returns_json_parsable_from_plaintext(self):
        http_getter = GetterFactory.from_string(
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/unit/tree_config.json"
        )
        resp_text = Path("tests/testdata/unit/tree_config.json").read_text()
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/unit/tree_config.json",
            resp_text,
        )
        content = http_getter.get_json()
        assert "priority_dict" in content

    @responses.activate
    def test_get_returns_yaml_parsable_from_plaintext(self):
        http_getter = GetterFactory.from_string(
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/config/config.yml"
        )
        resp_text = Path("tests/testdata/config/config.yml").read_text()
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/config/config.yml",
            resp_text,
        )
        content = http_getter.get_yaml()
        assert "pipeline" in content
        assert "input" in content
        assert "output" in content

    @responses.activate
    def test_sends_logprep_version_in_user_agent(self):
        resp_text = Path("tests/testdata/config/config.yml").read_text()
        logprep_version = get_versions().get("version")
        responses.add(
            responses.GET,
            "https://the-target/file",
            resp_text,
            {"User-Agent": f"Logprep version {logprep_version}"},
        )
        http_getter = GetterFactory.from_string("https://the-target/file")
        http_getter.get()

    @responses.activate
    def test_provides_oauth_compliant_headers(self):
        logprep_version = get_versions().get("version")
        responses.add(
            responses.GET,
            "https://the.target.url/targetfile",
            "",
            {
                "User-Agent": f"Logprep version {logprep_version}",
                "Authorization": "Bearer ajhsdfpoweiurjdfs239487",
            },
        )
        http_getter = GetterFactory.from_string(
            "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
        )
        http_getter.get()

    @responses.activate
    def test_provides_basic_authentication(self):
        responses.add(
            responses.GET,
            "https://the.target.url/targetfile",
        )
        http_getter = GetterFactory.from_string(
            "https://myusername:mypassword@the.target.url/targetfile"
        )
        http_getter.get()
        assert http_getter._sessions["the.target.url"].auth == HTTPBasicAuth(
            "myusername", "mypassword"
        )

    @responses.activate
    def test_raises_requestexception_after_3_retries(self):
        responses.add(responses.GET, "https://does-not-matter", Timeout())
        http_getter = GetterFactory.from_string("https://does-not-matter")
        with pytest.raises(Timeout):
            http_getter.get()
        responses.assert_call_count("https://does-not-matter", 3)
