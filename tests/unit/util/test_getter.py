# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import os
from pathlib import Path
from unittest import mock

import pytest
import requests.exceptions
import responses
from requests.auth import HTTPBasicAuth
from responses import matchers
from ruamel.yaml import YAML

from logprep._version import get_versions
from logprep.abc.credentials import Credentials
from logprep.factory_error import InvalidConfigurationError
from logprep.util.configuration import Configuration
from logprep.util.credentials import (
    BasicAuthCredentials,
    OAuth2ClientFlowCredentials,
    OAuth2PasswordFlowCredentials,
    OAuth2TokenCredentials,
)
from logprep.util.getter import (
    FileGetter,
    GetterFactory,
    GetterNotFoundError,
    HttpGetter,
)
from tests.testdata.metadata import path_to_config

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

    @pytest.mark.parametrize(
        "testcase, credential_file_content, instance, error",
        [
            (
                "Return BasicAuthCredential object",
                """---
"https://some.url":
    username: test
    password: test
""",
                BasicAuthCredentials,
                None,
            ),
            (
                "Return OAuthPasswordFlowCredential object",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    username: test
    password: test
""",
                OAuth2PasswordFlowCredentials,
                None,
            ),
            (
                "Return OAuthClientFlowCredential object",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    client_id: test
    client_secret: test
""",
                OAuth2ClientFlowCredentials,
                None,
            ),
            (
                "Return OAuthTokenCredential object",
                """---
"https://some.url":
    token: "jsoskdmoiewjdoeijkxsmoiqw8jdiowd0"
""",
                OAuth2TokenCredentials,
                None,
            ),
            (
                "Return None if credentials are missing",
                """---
"https://some.url":
""",
                type(None),
                None,
            ),
            (
                "Return None if wrong URL is given",
                """---
"https://some.other.url":
    token: "jsoskdmoiewjdoeijkxsmoiqw8jdiowd0"
""",
                type(None),
                None,
            ),
            (
                "Raises InvalidConfigurationError credentials file is invalid yml",
                """---
"https://some.url":
    password no colon here
    username: test
    endpoint: https://endpoint.end
""",
                None,
                InvalidConfigurationError,
            ),
            (
                "Return OAuthClientFlowCredential object when credentials file is valid json",
                """
{
    "https://some.url": {
        "endpoint": "https://endpoint.end",
        "client_id": "test",
        "client_secret": "test"
    }
}
""",
                OAuth2ClientFlowCredentials,
                None,
            ),
            (
                "Raise InvalidConfigurationError when credentials file is invalid json",
                """
{
    "https://some.url": 
        "endpoint": "https://endpoint.end",
        "client_id": "test",
        "client_secret": "test"
""",
                None,
                InvalidConfigurationError,
            ),
            (
                "Return OAuth2PassowordFlowCredentials object with additional client_id in credentials file",
                """---
"https://some.url": 
    endpoint: https://endpoint.end
    client_id: test
    username: test
    password: test
""",
                OAuth2PasswordFlowCredentials,
                None,
            ),
            (
                "Return OAuthTokenCredential object when username, passowrd, client_id and client_secret are also given",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    client_id: test
    username: test
    client_secret: test
    password: test
    token: "73475289038didjhwxnwnxwoiencn"

""",
                OAuth2TokenCredentials,
                None,
            ),
            (
                "Raise InvalidConfigurationError if credentials have wrong type",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    username: 123
    password: test
    client_secret: 456

""",
                None,
                InvalidConfigurationError,
            ),
            (
                "Return OAuthClientFlowCredential object when username passowrd are also given",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    client_id: test
    username: test
    password: test
    client_secret: test
""",
                OAuth2ClientFlowCredentials,
                None,
            ),
            (
                "Return None if no matching credentials class is found",
                """---
"https://some.url":
    endpoint: https://endpoint.end
    username: test
    client_secret: test
""",
                type(None),
                None,
            ),
        ],
    )
    def test_credentials_returns_expected_credential_object(
        self, testcase, credential_file_content, instance, tmp_path, error
    ):
        credential_file_path = tmp_path / "credentials"
        credential_file_path.write_text(credential_file_content)
        mock_env = {"LOGPREP_CREDENTIALS_FILE": str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url/configuration")
            if error is not None:
                with pytest.raises(error):
                    creds = http_getter.credentials
            else:
                creds = http_getter.credentials
                assert isinstance(creds, instance), testcase

    def test_credentials_returns_none_if_env_not_set(self):
        http_getter = GetterFactory.from_string("https://some.url/configuration")
        creds = http_getter.credentials
        assert creds is None

    def test_credentials_from_root_url(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
"http://some.url":
    endpoint: https://endpoint.end
    client_id: test
    client_secret: test
"""
        )
        mock_env = {"LOGPREP_CREDENTIALS_FILE": str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("http://some.url")
            creds = http_getter.credentials
            assert isinstance(creds, OAuth2ClientFlowCredentials)

    def test_credentials_is_none_on_invalid_credentials_file_path(self):
        mock_env = {"LOGPREP_CREDENTIALS_FILE": "this is something useless"}
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url")
            with pytest.raises(InvalidConfigurationError, match=r"wrong credentials file path"):
                creds = http_getter.credentials
                assert creds is None
