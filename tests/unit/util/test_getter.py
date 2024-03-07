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

    @responses.activate
    def test_provides_oauth_compliant_headers_if_token_is_set_via_env(self):
        mock_env = {
            "LOGPREP_CONFIG_AUTH_METHOD": "oauth",
            "LOGPREP_CONFIG_AUTH_TOKEN": "ajhsdfpoweiurjdfs239487",
        }

        logprep_version = get_versions().get("version")
        responses.get(
            url="https://the.target.url/targetfile",
            match=[
                matchers.header_matcher(
                    {
                        "User-Agent": f"Logprep version {logprep_version}",
                        "Authorization": "Bearer ajhsdfpoweiurjdfs239487",
                    },
                    strict_match=True,
                )
            ],
        )
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://the.target.url/targetfile")
            http_getter.get()

    def test_raises_on_try_to_set_credentials_from_url_string(self):
        with pytest.raises(
            NotImplementedError, match="Basic auth credentials via commandline are not supported"
        ):
            _ = GetterFactory.from_string(
                "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
            )

    # ToDo:
    #  - add tests for basic auth with multiple getter requests (urls)
    #  - add tests for basic auth and oauth token with multiple getter requests (urls)
    #  - add tests for basic auth and oauth workflow with multiple getter requests (urls)
    #  - add tests for oauth token and oauth workflow with multiple getter requests (urls)
    #  - add some acceptance test for logprep cli (test_run_logprep)
    #  -> maybe define an external resource that defines all credentials per source. something like:
    #        https://fda.de:
    #            method: auth
    #            client: ..
    #        https://ucl.de:
    #            method: basic
    #            user: ..
    #            password: ..
    #        https://seccmd.de:
    #            ...
    # option1: logprep run --creds credentials.yaml fda.de/... gitlab.de/...
    # option2: logprep run fda.de/... gitlab.de/...  [ENV: LOGPREP_CREDENTIAL_FILE=file.yml]

    @responses.activate
    def test_provides_basic_authentication_creds_from_environment(self):
        mock_env = {
            "LOGPREP_CONFIG_AUTH_0_METHOD": "basic",
            "LOGPREP_CONFIG_AUTH_0_USERNAME": "myusername",
            "LOGPREP_CONFIG_AUTH_0_PASSWORD": "mypassword",
        }
        responses.add(
            responses.GET,
            "https://the.target.url/targetfile",
        )
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://the.target.url/targetfile")
            http_getter.get()
        assert http_getter._sessions["the.target.url"].auth == HTTPBasicAuth(
            "myusername", "mypassword"
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

    @responses.activate
    def test_get_requests_an_oauth2_endpoint(self):
        mock_env = {
            "LOGPREP_OAUTH2_0_ENDPOINT": "https://some.url/oauth/token",
            "LOGPREP_OAUTH2_0_GRANT_TYPE": "password",
            "LOGPREP_OAUTH2_0_USERNAME": "test_user",
            "LOGPREP_OAUTH2_0_PASSWORD": "test_password",
            "LOGPREP_OAUTH2_0_CLIENT_ID": "client_id",
            "LOGPREP_OAUTH2_0_CLIENT_SECRET": "client_secret",
        }
        # get the access token
        responses.post(
            url="https://some.url/oauth/token",
            json={
                "access_token": "hoahsknakalamslkoas",
                "expires_in": 1337,
                "refresh_expires_in": 1800,
                "refresh_token": "IsInR5cCIgOiAiSldUI",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "5c9a3102-f0de-4f55-abd7-4f1773ad26b6",
                "scope": "profile email",
            },
            status=200,
        )
        # get resource with access token
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some resource",
            status=200,
        )

        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url/configuration")
            resp = http_getter.get()
        assert "some resource" in resp

    @responses.activate
    def test_get_requests_two_different_resources_with_different_oauth2_token(self):
        mock_env = {
            "LOGPREP_OAUTH2_0_ENDPOINT": "https://some.url/oauth/token",
            "LOGPREP_OAUTH2_0_GRANT_TYPE": "password",
            "LOGPREP_OAUTH2_0_USERNAME": "test_user",
            "LOGPREP_OAUTH2_0_PASSWORD": "test_password",
            "LOGPREP_OAUTH2_0_CLIENT_ID": "client_id",
            "LOGPREP_OAUTH2_0_CLIENT_SECRET": "client_secret",
            "LOGPREP_OAUTH2_1_ENDPOINT": "https://some-other.url/openid/connect/token",
            "LOGPREP_OAUTH2_1_GRANT_TYPE": "stronger-password",
            "LOGPREP_OAUTH2_1_USERNAME": "second_test_user",
            "LOGPREP_OAUTH2_1_PASSWORD": "second_test_password",
        }
        # get the access token from https://some.url/oauth/token
        responses.post(
            url="https://some.url/oauth/token",
            json={
                "access_token": "hoahsknakalamslkoas",
                "expires_in": 1337,
                "refresh_expires_in": 1800,
                "refresh_token": "IsInR5cCIgOiAiSldUI",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "5c9a3102-f0de-4f55-abd7-4f1773ad26b6",
                "scope": "profile email",
            },
            status=200,
        )
        # get the access token from https://some-other.url/openid/connect/token
        responses.post(
            url="https://some-other.url/openid/connect/token",
            json={
                "access_token": "nR5cCIgnR5cCIgnR5cCIg",
                "expires_in": 600,
                "refresh_expires_in": 1800,
                "refresh_token": "iSldUiSldUiSldUiSldU",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "faee38b2-d5ce-4cc8-ade3-ed3fcd82cf39",
                "scope": "profile email",
            },
            status=200,
        )
        # get first resource with access token
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some resource",
            status=200,
        )
        # get second resource with wrong access token from first resource (during search of valid token)
        responses.get(
            url="https://some-other.url/second-resource",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some other resource",
            status=401,  # unauthorized due to wrong token
        )
        # get second resource with correct access token
        responses.get(
            url="https://some-other.url/second-resource",
            match=[matchers.header_matcher({"Authorization": "Bearer nR5cCIgnR5cCIgnR5cCIg"})],
            json="some other resource",
            status=200,
        )

        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url/configuration")
            resp = http_getter.get()
            assert "some resource" in resp
            http_getter = GetterFactory.from_string("https://some-other.url/second-resource")
            resp = http_getter.get()
            assert "some other resource" in resp

    @mock.patch("logprep.util.getter.HttpGetter._get_oauth_token")
    @mock.patch("urllib3.connectionpool.HTTPConnectionPool._get_conn")
    def test_get_calls_get_oauth_token_on_401_response(self, getconn_mock, get_oauth_token_mock):
        getconn_mock.return_value.getresponse.side_effect = [
            mock.MagicMock(
                status=401
            ),  # two responses one for the first attempt and then a second to retry
            mock.MagicMock(status=401),
        ]
        http_getter = GetterFactory.from_string("https://does-not-matter/bar")
        with pytest.raises(requests.exceptions.RequestException, match="401 Client Error"):
            http_getter.get()
        get_oauth_token_mock.assert_called_once()

    @responses.activate
    def test_get_raises_with_invalid_token(self):
        mock_env = {
            "LOGPREP_OAUTH2_0_ENDPOINT": "https://some.url/oauth/token",
            "LOGPREP_OAUTH2_0_GRANT_TYPE": "password",
            "LOGPREP_OAUTH2_0_USERNAME": "test_user",
            "LOGPREP_OAUTH2_0_PASSWORD": "test_password",
            "LOGPREP_OAUTH2_0_CLIENT_ID": "client_id",
            "LOGPREP_OAUTH2_0_CLIENT_SECRET": "client_secret",
        }
        # get the invalid access token
        responses.post(
            url="https://some.url/oauth/token",
            json={
                "access_token": "hoahsknakalamslkoas",
                "expires_in": 1337,
                "refresh_expires_in": 1800,
                "refresh_token": "IsInR5cCIgOiAiSldUI",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "5c9a3102-f0de-4f55-abd7-4f1773ad26b6",
                "scope": "profile email",
            },
            status=200,  # successful request for a token
        )
        # get configuration with access token
        config = Configuration.from_sources([path_to_config])
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json=config.as_dict(),
            status=401,  # request token is not valid, result in unauthorized 401
        )
        with pytest.raises(requests.exceptions.RequestException, match="No valid token found"):
            with mock.patch.dict("os.environ", mock_env):
                http_getter = GetterFactory.from_string("https://some.url/configuration")
                http_getter.get()

    @responses.activate
    def test_get_resource_after_token_expires(self):
        mock_env = {
            "LOGPREP_OAUTH2_0_ENDPOINT": "https://some.url/oauth/token",
            "LOGPREP_OAUTH2_0_GRANT_TYPE": "password",
            "LOGPREP_OAUTH2_0_USERNAME": "test_user",
            "LOGPREP_OAUTH2_0_PASSWORD": "test_password",
            "LOGPREP_OAUTH2_0_CLIENT_ID": "client_id",
            "LOGPREP_OAUTH2_0_CLIENT_SECRET": "client_secret",
        }
        # get first valid access token
        responses.post(
            url="https://some.url/oauth/token",
            json={
                "access_token": "hoahsknakalamslkoas",
                "expires_in": 1337,
                "refresh_expires_in": 1800,
                "refresh_token": "IsInR5cCIgOiAiSldUI",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "5c9a3102-f0de-4f55-abd7-4f1773ad26b6",
                "scope": "profile email",
            },
            status=200,
        )
        # get valid access token (by searching the list of tokens)
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some resource",
            status=200,
        )
        # get resource with valid access token
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some resource",
            status=200,
        )
        # get resource again with token that has expired over time
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer hoahsknakalamslkoas"})],
            json="some resource",
            status=401,  # token has expired
        )
        # get new second valid access token
        responses.post(
            url="https://some.url/oauth/token",
            json={
                "access_token": "R5cCIgOR5cCIgOR5cCIg",
                "expires_in": 1337,
                "refresh_expires_in": 1800,
                "refresh_token": "IsInR5cCIgOiAiSldUI",
                "token_type": "Bearer",
                "not-before-policy": 0,
                "session_state": "5c9a3102-f0de-4f55-abd7-4f1773ad26b6",
                "scope": "profile email",
            },
            status=200,
        )
        # get valid access token (by searching the list of tokens)
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer R5cCIgOR5cCIgOR5cCIg"})],
            json="some resource",
            status=200,
        )
        # get resource again with second valid token
        responses.get(
            url="https://some.url/configuration",
            match=[matchers.header_matcher({"Authorization": "Bearer R5cCIgOR5cCIgOR5cCIg"})],
            json="some resource",
            status=200,
        )

        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url/configuration")
            resp = http_getter.get()
            assert "some resource" in resp
            resp = http_getter.get()
            assert "some resource" in resp

    @responses.activate
    def test_get_raises_401_if_no_token_is_received(self):
        mock_env = {
            "LOGPREP_OAUTH2_0_ENDPOINT": "https://some.url/oauth/token",
            "LOGPREP_OAUTH2_0_GRANT_TYPE": "password",
            "LOGPREP_OAUTH2_0_USERNAME": "test_user",
            "LOGPREP_OAUTH2_0_PASSWORD": "test_password",
            "LOGPREP_OAUTH2_0_CLIENT_ID": "client_id",
            "LOGPREP_OAUTH2_0_CLIENT_SECRET": "client_secret",
        }
        # get the access token
        responses.post(url="https://some.url/oauth/token", json={"no": "token info"}, status=200)
        # get resource
        responses.get(
            url="https://some.url/configuration",
            match=[
                matchers.header_matcher(
                    {
                        "Accept": "*/*",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                        "User-Agent": f"Logprep version {get_versions().get('version')}",
                    },
                    strict_match=True,
                )
            ],
            status=401,
        )

        with pytest.raises(
            requests.exceptions.RequestException, match="401 Client Error: Unauthorized for url"
        ):
            with mock.patch.dict("os.environ", mock_env):
                http_getter = GetterFactory.from_string("https://some.url/configuration")
                http_getter.get()

    @pytest.mark.parametrize(
        "testcase, credential_file_content, instance",
        [
            (
                "Return BasicAuthCredential object",
                """---
"https://some.url":
    username: test
    password: test
""",
                BasicAuthCredentials,
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
            ),
            (
                "Return OAuthTokenCredential object",
                """---
"https://some.url":
    token: "jsoskdmoiewjdoeijkxsmoiqw8jdiowd0"
""",
                OAuth2TokenCredentials,
            ),
        ],
    )
    def test_credentials_returns_credential_object(
        self, testcase, credential_file_content, instance, tmp_path
    ):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(credential_file_content)
        mock_env = {"LOGPREP_CREDENTIALS_FILE": str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter = GetterFactory.from_string("https://some.url/configuration")
            creds = http_getter.credentials
            assert isinstance(creds, instance), testcase
