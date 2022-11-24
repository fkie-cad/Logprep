# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import json
from pathlib import Path
from unittest import mock

import pytest
from requests.auth import HTTPBasicAuth
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
            ("http://user:password@my/file", "http", "user:password@my/file"),
            ("https://user:password@my/file", "https", "user:password@my/file"),
            (
                "http://oauth:ajpf0q9vrfásdjlk__234d@my/file",
                "http",
                "oauth:ajpf0q9vrfásdjlk__234d@my/file",
            ),
            (
                "https://oauth:ajpf0q9vrfásdjlk__234d@my/file",
                "https",
                "oauth:ajpf0q9vrfásdjlk__234d@my/file",
            ),
        ],
    )
    def test_from_string_sets_protocol_and_target(
        self, target_string, expected_protocol, expected_target
    ):
        my_getter = GetterFactory.from_string(target_string)
        assert my_getter.protocol == expected_protocol
        assert my_getter.target == expected_target


class TestFileGetter:
    def test_factory_returns_file_getter_without_protocol(self):
        file_getter = GetterFactory.from_string("/my/file")
        assert isinstance(file_getter, FileGetter)

    def test_factory_returns_file_getter_with_protocol(self):
        file_getter = GetterFactory.from_string("file:///my/file")
        assert isinstance(file_getter, FileGetter)

    def test_get_returns_content(self):
        file_getter = GetterFactory.from_string("/my/file")
        with mock.patch("io.open", mock.mock_open(read_data="my content")):
            content = file_getter.get()
            assert content == "my content"

    @pytest.mark.parametrize(
        "method_name, input_content, expected_output",
        [
            (
                "get_yaml",
                """---
first_dict:
    key:
        - valid_list_element
        - valid_list_element
                """,
                {"first_dict": {"key": ["valid_list_element", "valid_list_element"]}},
            ),
            (
                "get_yaml",
                """---
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
                """{
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
                """{
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
                """[{
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
        ],
    )
    def test_parses_content(self, method_name, input_content, expected_output):
        file_getter = GetterFactory.from_string("/my/file")
        method = getattr(file_getter, method_name)
        with mock.patch("io.open", mock.mock_open(read_data=input_content)):
            output = method()
            assert output == expected_output


class TestHttpGetter:
    def test_factory_returns_http_getter_for_http(self):
        http_getter = GetterFactory.from_string("http://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    def test_factory_returns_http_getter_for_https(self):
        http_getter = GetterFactory.from_string("https://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    def test_get_returns_json_parsable_from_plaintext(self):
        http_getter = GetterFactory.from_string(
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/unit/tree_config.json"
        )
        resp_text = Path("tests/testdata/unit/tree_config.json").read_text()
        with mock.patch("requests.get") as mock_request_get:
            mock_request_get.return_value.text = resp_text
            content = json.loads(http_getter.get())
        assert "priority_dict" in content

    def test_get_returns_yaml_parsable_from_plaintext(self):
        http_getter = GetterFactory.from_string(
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/config/config.yml"
        )
        resp_text = Path("tests/testdata/config/config.yml").read_text()
        with mock.patch("requests.get") as mock_request_get:
            mock_request_get.return_value.text = resp_text
            content = yaml.load(http_getter.get())
        assert "pipeline" in content
        assert "input" in content
        assert "output" in content

    def test_sends_logprep_version_in_user_agent(self):
        http_getter = GetterFactory.from_string("https://the-target/file")
        resp_text = Path("tests/testdata/config/config.yml").read_text()
        with mock.patch("requests.get") as mock_request_get:
            mock_request_get.return_value.text = resp_text
            http_getter.get()
            logprep_version = get_versions().get("version")
            mock_request_get.assert_called_with(
                url="https://the-target/file",
                timeout=5,
                allow_redirects=True,
                headers={"User-Agent": f"Logprep version {logprep_version}"},
                auth=None,
            )

    def test_provides_oauth_compliant_headers(self):
        http_getter = GetterFactory.from_string(
            "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
        )
        with mock.patch("requests.get") as mock_request_get:
            http_getter.get()
            logprep_version = get_versions().get("version")
            mock_request_get.assert_called_with(
                url="https://the.target.url/targetfile",
                timeout=5,
                allow_redirects=True,
                headers={
                    "User-Agent": f"Logprep version {logprep_version}",
                    "Authorization": "Bearer ajhsdfpoweiurjdfs239487",
                },
                auth=None,
            )

    def test_provides_basic_authentication(self):
        http_getter = GetterFactory.from_string(
            "https://myusername:mypassword@the.target.url/targetfile"
        )
        with mock.patch("requests.get") as mock_request_get:
            http_getter.get()
            logprep_version = get_versions().get("version")
            auth = HTTPBasicAuth("myusername", "mypassword")
            mock_request_get.assert_called_with(
                url="https://the.target.url/targetfile",
                timeout=5,
                allow_redirects=True,
                headers={
                    "User-Agent": f"Logprep version {logprep_version}",
                },
                auth=auth,
            )
