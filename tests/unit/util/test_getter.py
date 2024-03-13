# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
import requests.exceptions
import responses
from responses import matchers
from ruamel.yaml import YAML

from logprep._version import get_versions
from logprep.util.credentials import Credentials
from logprep.util.getter import (
    FileGetter,
    GetterFactory,
    GetterNotFoundError,
    HttpGetter,
)

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
        ],
    )
    def test_from_string_sets_protocol_and_target(
        self, target_string, expected_protocol, expected_target
    ):
        my_getter = GetterFactory.from_string(target_string)
        assert my_getter.protocol == expected_protocol
        assert my_getter.target == expected_target

    def test_getter_expands_from_environment(self):
        os.environ["PYTEST_TEST_TARGET"] = "the-web-target"
        url = "https://${PYTEST_TEST_TARGET}"
        my_getter = GetterFactory.from_string(url)
        assert my_getter.target == "the-web-target"

    def test_getter_expands_environment_variables_in_content(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken"

    def test_getter_expands_setted_environment_variables_and_missing_to_blank(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        if "LOGPREP_MISSING_TOKEN" in os.environ:
            os.environ.pop("LOGPREP_MISSING_TOKEN")
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN, and this is my $LOGPREP_MISSING_TOKEN")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my "
        assert "LOGPREP_MISSING_TOKEN" in my_getter.missing_env_vars
        assert len(my_getter.missing_env_vars) == 1

    def test_getter_expands_only_uppercase_variable_names(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN, and this is my $pytest_test_token")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my $pytest_test_token"

    def test_getter_expands_setted_environment_variables_and_missing_to_blank_with_braced_variables(
        self, tmp_path
    ):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        if "LOGPREP_MISSING_TOKEN" in os.environ:
            os.environ.pop("LOGPREP_MISSING_TOKEN")
        testfile = tmp_path / "test_getter.json"
        testfile.write_text(
            "this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_MISSING_TOKEN}"
        )
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my "

    def test_getter_expands_only_uppercase_variable_names_with_braced_variables(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${not_a_token}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${not_a_token}"

    def test_getter_ignores_list_comparison_logprep_list_variable(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_LIST}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${LOGPREP_LIST}"
        assert len(my_getter.missing_env_vars) == 0

    def test_getter_ignores_list_comparison_logprep_list_variable_if_set(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        os.environ.update({"LOGPREP_LIST": "foo"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_LIST}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${LOGPREP_LIST}"
        assert len(my_getter.missing_env_vars) == 0

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

    def test_getter_expands_only_whitelisted_in_yaml_content(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text(
            """---
key: $PYTEST_TEST_TOKEN
list:
    - first element
    - $HOME
    - $PYTEST_TEST_TOKEN
    - ${PYTEST_TEST_TOKEN}-with-additional-string
dict: {key: value, second_key: $PYTEST_TEST_TOKEN}
"""
        )
        my_getter = GetterFactory.from_string(str(testfile))
        expected = {
            "key": "mytoken",
            "list": ["first element", "$HOME", "mytoken", "mytoken-with-additional-string"],
            "dict": {"key": "value", "second_key": "mytoken"},
        }
        assert my_getter.get_yaml() == expected

    def test_getter_does_not_reduces_double_dollar_for_unvalid_prefixes(self, tmp_path):
        os.environ.update({"PYTEST_TEST_TOKEN": "mytoken"})
        os.environ.update({"LOGPREP_LIST": "foo"})
        testfile = tmp_path / "test_getter.json"
        testfile.write_text(
            "this is my $PYTEST_TEST_TOKEN, and this is my $$UNVALID_PREFIXED_TOKEN"
        )
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my $$UNVALID_PREFIXED_TOKEN"
        assert len(my_getter.missing_env_vars) == 0


class TestFileGetter:
    def test_factory_returns_file_getter_without_protocol(self):
        file_getter = GetterFactory.from_string("/my/file")
        assert isinstance(file_getter, FileGetter)

    def test_factory_returns_file_getter_with_protocol(self):
        file_getter = GetterFactory.from_string("file:///my/file")
        assert isinstance(file_getter, FileGetter)

    def test_get_returns_content(self):
        file_getter = GetterFactory.from_string("/my/file")
        with mock.patch("pathlib.Path.open", mock.mock_open(read_data=b"my content")) as _:
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

    def test_raises_on_try_to_set_credentials_from_url_string(self):
        with pytest.raises(
            NotImplementedError, match="Basic auth credentials via commandline are not supported"
        ):
            _ = GetterFactory.from_string(
                "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
            )

    @mock.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")
    def test_raises_requestexception_after_3_retries(self, getconn_mock):
        getconn_mock.return_value.getresponse.side_effect = [
            mock.MagicMock(status=500),  # one initial request and three retries
            mock.MagicMock(status=502),
            mock.MagicMock(status=500),
            mock.MagicMock(status=500),
            mock.MagicMock(status=500),  # fourth is not considered because of raise
        ]
        http_getter = GetterFactory.from_string("https://does-not-matter/bar")
        with pytest.raises(requests.exceptions.RequestException, match="Max retries exceed"):
            http_getter.get()
        assert getconn_mock.return_value.request.mock_calls == [
            # one initial request and three retries
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
        ]

    @mock.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")
    def test_get_does_one_successful_request_after_two_failed(self, getconn_mock):
        getconn_mock.return_value.getresponse.side_effect = [
            mock.MagicMock(status=500),
            mock.MagicMock(status=502),
            mock.MagicMock(status=200),
        ]
        http_getter = GetterFactory.from_string("https://does-not-matter/bar")
        http_getter.get()
        assert getconn_mock.return_value.request.mock_calls == [
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
            mock.call("GET", "/bar", body=None, headers=mock.ANY),
        ]

    def test_credentials_returns_credential_object_if_no_credentials(self):
        http_getter = GetterFactory.from_string("https://does-not-matter/bar")
        assert isinstance(http_getter.credentials, Credentials)

    def test_credentials_returns_credentials_if_set(self, tmp_path):
        credentials_file_content = {
            "https://does-not-matter": {
                "username": "myuser",
                "password": "mypassword",
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        os.environ["LOGPREP_CREDENTIALS_FILE"] = str(credentials_file)
        http_getter = GetterFactory.from_string("https://does-not-matter/bar")
        assert isinstance(http_getter.credentials, Credentials)

    @responses.activate
    def test_get_raw_gets_token_before_request(self, tmp_path):
        responses.add(
            responses.POST,
            "https://the.krass.endpoint/token",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
        )
        responses.add(
            responses.GET,
            "https://does-not-matter/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "https://does-not-matter": {
                "username": "myuser",
                "password": "mypassword",
                "endpoint": "https://the.krass.endpoint/token",
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict("os.environ", {"LOGPREP_CREDENTIALS_FILE": str(credentials_file)}):
            http_getter = GetterFactory.from_string("https://does-not-matter/bar")
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count("https://does-not-matter/bar", 1)

    @responses.activate
    def test_get_raw_reuses_existing_session(self, tmp_path):
        responses.add(
            responses.POST,
            "https://the.krass.endpoint/token",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
        )
        responses.add(
            responses.GET,
            "https://does-not-matter/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "https://does-not-matter": {
                "username": "myuser",
                "password": "mypassword",
                "endpoint": "https://the.krass.endpoint/token",
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict("os.environ", {"LOGPREP_CREDENTIALS_FILE": str(credentials_file)}):
            http_getter = GetterFactory.from_string("https://does-not-matter/bar")
            return_content = http_getter.get_json()
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count("https://does-not-matter/bar", 2)

    @responses.activate
    def test_get_raw_refreshes_token_if_expired(self, tmp_path):
        responses.add(
            responses.POST,
            "https://the.krass.endpoint/token",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
        )
        responses.add(
            responses.GET,
            "https://does-not-matter/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "https://does-not-matter": {
                "username": "myuser",
                "password": "mypassword",
                "endpoint": "https://the.krass.endpoint/token",
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict("os.environ", {"LOGPREP_CREDENTIALS_FILE": str(credentials_file)}):
            http_getter: HttpGetter = GetterFactory.from_string("https://does-not-matter/bar")
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count("https://does-not-matter/bar", 1)
            # expire token
            http_getter.credentials._token.expiry_time = datetime.now() - timedelta(seconds=3600)
            return_content = http_getter.get_json()
