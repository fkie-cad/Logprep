# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=unspecified-encoding
# pylint: disable=protected-access
import json
import uuid
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest
import requests.exceptions
import responses
from responses import matchers
from responses.registries import OrderedRegistry
from ruamel.yaml import YAML

from logprep.util.credentials import Credentials, CredentialsEnvNotFoundError
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE, ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import (
    FileGetter,
    GetterFactory,
    GetterNotFoundError,
    HttpGetter,
)

yaml = YAML(pure=True, typ="safe")


@pytest.fixture(autouse=True)
def fixture_clear_getter_cache():
    getter = HttpGetter(protocol="http", target="anything")
    getter._shared.clear()


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

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TARGET": "the-web-target"})
    def test_getter_expands_from_environment(self):
        url = "https://${PYTEST_TEST_TARGET}"
        my_getter = GetterFactory.from_string(url)
        assert my_getter.target == "the-web-target"

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_environment_variables_in_content(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken"

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_setted_environment_variables_and_missing_to_blank(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN, and this is my $LOGPREP_MISSING_TOKEN")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my "
        assert "LOGPREP_MISSING_TOKEN" in my_getter.missing_env_vars
        assert len(my_getter.missing_env_vars) == 1

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_only_uppercase_variable_names(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my $PYTEST_TEST_TOKEN, and this is my $pytest_test_token")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my $pytest_test_token"

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_setted_environment_variables_and_missing_to_blank_with_braced_variables(
        self, tmp_path
    ):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text(
            "this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_MISSING_TOKEN}"
        )
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my "

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_only_uppercase_variable_names_with_braced_variables(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${not_a_token}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${not_a_token}"

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_ignores_list_comparison_logprep_list_variable(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_LIST}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${LOGPREP_LIST}"
        assert len(my_getter.missing_env_vars) == 0

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken", "LOGPREP_LIST": "foo"})
    def test_getter_ignores_list_comparison_logprep_list_variable_if_set(self, tmp_path):
        testfile = tmp_path / "test_getter.json"
        testfile.write_text("this is my ${PYTEST_TEST_TOKEN}, and this is my ${LOGPREP_LIST}")
        my_getter = GetterFactory.from_string(str(testfile))
        assert my_getter.get() == "this is my mytoken, and this is my ${LOGPREP_LIST}"
        assert len(my_getter.missing_env_vars) == 0

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_environment_variables_in_yaml_content(self, tmp_path):
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

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken"})
    def test_getter_expands_only_whitelisted_in_yaml_content(self, tmp_path):
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

    @mock.patch.dict("os.environ", {"PYTEST_TEST_TOKEN": "mytoken", "LOGPREP_LIST": "foo"})
    def test_getter_does_not_reduces_double_dollar_for_unvalid_prefixes(self, tmp_path):
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
            (
                "get_yaml",
                b"""""",
                {},
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
        http_getter: HttpGetter = GetterFactory.from_string("http://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    def test_factory_returns_http_getter_for_https(self):
        http_getter: HttpGetter = GetterFactory.from_string("https://testfile.json")
        assert isinstance(http_getter, HttpGetter)

    @responses.activate
    def test_get_returns_json_parsable_from_plaintext(self):
        http_getter: HttpGetter = GetterFactory.from_string(
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
        http_getter: HttpGetter = GetterFactory.from_string(
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
        logprep_version = version("logprep")
        responses.add(
            responses.GET,
            "https://the-target/file",
            resp_text,
            {"User-Agent": f"Logprep version {logprep_version}"},
        )
        http_getter: HttpGetter = GetterFactory.from_string("https://the-target/file")
        http_getter.get()

    def test_raises_on_try_to_set_credentials_from_url_string(self):
        with pytest.raises(
            NotImplementedError, match="Basic auth credentials via commandline are not supported"
        ):
            _ = GetterFactory.from_string(
                "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
            )

    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    @responses.activate(registry=OrderedRegistry)
    def test_raises_requestexception_after_3_retries(self):
        responses.get("https://does-not-matter/bar", status=500)
        responses.get("https://does-not-matter/bar", status=500)  # 1st retry
        responses.get("https://does-not-matter/bar", status=502)  # 2nd retry
        responses.get("https://does-not-matter/bar", status=500)  # 3rd retry and exception
        responses.get("https://does-not-matter/bar", status=200)  # works again
        http_getter: HttpGetter = GetterFactory.from_string("https://does-not-matter/bar")
        with pytest.raises(requests.exceptions.RequestException, match="Max retries exceed"):
            http_getter.get()
        http_getter.get()

    @responses.activate(registry=OrderedRegistry)
    def test_get_does_one_successful_request_after_two_failed(self):
        responses.get("https://does-not-matter/bar", status=500)
        responses.get("https://does-not-matter/bar", status=500)  # 1st retry
        responses.get("https://does-not-matter/bar", status=502)  # 2nd retry
        responses.get("https://does-not-matter/bar", status=200)  # works again
        http_getter: HttpGetter = GetterFactory.from_string("https://does-not-matter/bar")
        http_getter.get()

    def test_credentials_returns_credential_object_if_no_credentials(self):
        http_getter: HttpGetter = GetterFactory.from_string("https://does-not-matter/bar")
        assert isinstance(http_getter.credentials, Credentials)

    def test_credentials_returns_credentials_if_set(self, tmp_path):
        credentials_file_content = {
            "getter": {
                "https://does-not-matter": {
                    "username": "myuser",
                    "password": "mypassword",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict(
            "os.environ", {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        ):
            http_getter: HttpGetter = GetterFactory.from_string("https://does-not-matter/bar")
            assert isinstance(http_getter.credentials, Credentials)

    @responses.activate
    def test_get_raw_gets_token_before_request(self, tmp_path):
        domain = str(uuid.uuid4())
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
            f"https://{domain}/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "username": "myuser",
                    "password": "mypassword",
                    "endpoint": "https://the.krass.endpoint/token",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict(
            "os.environ", {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        ):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count(f"https://{domain}/bar", 1)

    @responses.activate
    def test_get_raw_reuses_existing_session(self, tmp_path):
        domain = str(uuid.uuid4())
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
            f"https://{domain}/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "username": "myuser",
                    "password": "mypassword",
                    "endpoint": "https://the.krass.endpoint/token",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict(
            "os.environ", {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        ):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            http_getter.get_json()
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count(f"https://{domain}/bar", 2)

    @responses.activate
    def test_get_raw_refreshes_token_if_expired(self, tmp_path):
        domain = str(uuid.uuid4())
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
            f"https://{domain}/bar",
            json={"key": "the cooooontent"},
            match=[matchers.header_matcher({"Authorization": "Bearer toooooken"})],
        )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "username": "myuser",
                    "password": "mypassword",
                    "endpoint": "https://the.krass.endpoint/token",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        with mock.patch.dict(
            "os.environ", {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        ):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            return_content = http_getter.get_json()
            assert return_content == {"key": "the cooooontent"}
            responses.assert_call_count("https://the.krass.endpoint/token", 1)
            responses.assert_call_count(f"https://{domain}/bar", 1)
            # expire token
            http_getter._credentials_registry.get(
                f"https://{domain}"
            )._token.expiry_time = datetime.now() - timedelta(seconds=3600)
            return_content = http_getter.get_json()

    @responses.activate
    def test_get_raw_raises_if_credential_file_env_not_set_and_unauthorizes(self):
        domain = str(uuid.uuid4())
        responses.add(
            responses.GET,
            f"https://{domain}/bar",
            status=401,
        )
        with pytest.raises(CredentialsEnvNotFoundError):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            http_getter.get_json()

    @responses.activate
    def test_get_raw_raises_if_credential_file_env_set_and_unauthorizes(self):
        domain = str(uuid.uuid4())
        responses.add(
            responses.GET,
            f"https://{domain}/bar",
            status=401,
        )
        with pytest.raises(requests.exceptions.HTTPError) as error:
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            with mock.patch.dict(
                "os.environ",
                {ENV_NAME_LOGPREP_CREDENTIALS_FILE: "examples/exampledata/config/credentials.yml"},
            ):
                http_getter.get_json()
        assert error.value.response.status_code == 401

    @responses.activate
    def test_get_raw_uses_mtls_and_session_cert_is_set_and_used_in_request(self, tmp_path):
        domain = str(uuid.uuid4())
        with responses.RequestsMock(assert_all_requests_are_fired=False):
            req_kwargs = {
                "cert": ("path/to/cert", "path/to/key"),
                "verify": True,
            }
            responses.add(
                responses.GET,
                url=f"https://{domain}/bar",
                match=[matchers.request_kwargs_matcher(req_kwargs)],
            )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "client_key": "path/to/key",
                    "cert": "path/to/cert",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            http_getter.get_raw()
            assert isinstance(http_getter.credentials, Credentials)
            assert (
                "path/to/cert"
                in http_getter._credentials_registry.get(f"https://{domain}")._session.cert
            )

    @responses.activate
    def test_get_raw_uses_mtls_with_session_cert_and_ca_cert(self, tmp_path):
        domain = str(uuid.uuid4())
        req_kwargs = {
            "cert": ("path/to/cert", "path/to/key"),
            "verify": "path/to/ca/cert",
        }
        responses.add(
            responses.GET,
            url=f"https://{domain}/bar",
            match=[matchers.request_kwargs_matcher(req_kwargs)],
        )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "client_key": "path/to/key",
                    "cert": "path/to/cert",
                    "ca_cert": "path/to/ca/cert",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            http_getter.get_raw()
            assert isinstance(http_getter.credentials, Credentials)
            assert (
                "path/to/cert"
                in http_getter._credentials_registry.get(f"https://{domain}")._session.cert
            )
            assert (
                "path/to/ca/cert"
                in http_getter._credentials_registry.get(f"https://{domain}")._session.verify
            )
            session = http_getter._credentials_registry.get(f"https://{domain}")._session
            assert session.cert == ("path/to/cert", "path/to/key")
            assert session.verify == "path/to/ca/cert"

    @responses.activate
    def test_get_raw_reuses_mtls_session_and_ca_cert_is_not_updated(self, tmp_path):
        domain = str(uuid.uuid4())
        req_kwargs = {
            "cert": ("path/to/cert", "path/to/key"),
            "verify": "path/to/ca/cert",
        }
        responses.add(
            responses.GET,
            url=f"https://{domain}/bar",
            match=[matchers.request_kwargs_matcher(req_kwargs)],
        )
        credentials_file_content = {
            "getter": {
                f"https://{domain}": {
                    "client_key": "path/to/key",
                    "cert": "path/to/cert",
                    "ca_cert": "path/to/ca/cert",
                }
            }
        }
        credentials_file: Path = tmp_path / "credentials.json"
        credentials_file.write_text(json.dumps(credentials_file_content))
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credentials_file)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(f"https://{domain}/bar")
            http_getter.get_raw()
            credentials_file_content.popitem()
            credentials_file_content.update(
                {
                    f"https://{domain}": {
                        "cert": "path/to/other/cert",
                        "client_key": "path/to/client/key",
                        "ca_cert": "path/to/ca/cert/the/second",
                    }
                }
            )
            http_getter.get_raw()
            assert (
                "path/to/cert"
                in http_getter._credentials_registry.get(f"https://{domain}")._session.cert
            )
            assert (
                "path/to/ca/cert"
                in http_getter._credentials_registry.get(f"https://{domain}")._session.verify
            )
            session = http_getter._credentials_registry.get(f"https://{domain}")._session
            assert session.cert == ("path/to/cert", "path/to/key")
            assert session.verify == "path/to/ca/cert"

    @responses.activate
    def test_get_raw_always_requests_if_no_refresh_timer_was_set(self, tmp_path):
        url = f"https://{uuid.uuid4()}/bar"
        mock_response_1 = {"key": "the content 1"}
        mock_response_2 = {"key": "the content 2"}
        responses.add(responses.GET, url, json=mock_response_1)
        responses.add(responses.GET, url, json=mock_response_2)
        http_getter: HttpGetter = GetterFactory.from_string(url)

        assert http_getter.cache is None
        return_content_1 = http_getter.get_json()
        assert self._get_cache_as_json(http_getter) == return_content_1
        return_content_2 = http_getter.get_json()
        assert self._get_cache_as_json(http_getter) == return_content_2
        assert return_content_1 == mock_response_1
        assert return_content_2 == mock_response_2
        responses.assert_call_count(url, 2)

    @responses.activate
    def test_get_raw_always_requests_if_refresh_timer_is_zero(self, tmp_path):
        target = f"{uuid.uuid4()}"
        url = f"https://{target}"

        mock_response_1 = {"key": "the content 1"}
        mock_response_2 = {"key": "the content 2"}
        responses.add(responses.GET, url, json=mock_response_1)
        responses.add(responses.GET, url, json=mock_response_2)

        getter_file_content = {target: {"refresh_interval": 0}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            assert self._get_cache_as_json(http_getter) == return_content_1
            return_content_2 = http_getter.get_json()
            assert self._get_cache_as_json(http_getter) == return_content_2
            assert return_content_1 == mock_response_1
            assert return_content_2 == mock_response_2
            responses.assert_call_count(url, 2)

    @responses.activate
    def test_get_raw_raises_exception_if_refresh_interval_is_negative(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"

        getter_file_content = {target: {"refresh_interval": -1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            with pytest.raises(ValueError, match=r"'refresh_interval' must be >= 0: -1"):
                GetterFactory.from_string(url)

    @responses.activate
    def test_get_raw_sets_cache_before_job_runs_if_cache_is_not_initialized(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content"})

        getter_file_content = {target: {"refresh_interval": 100}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert len(http_getter.scheduler.jobs) == 1
            assert http_getter.scheduler.jobs[0].interval == 100

            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            assert self._get_cache_as_json(http_getter) == return_content_1
            assert return_content_1 == {"key": "the content"}
            responses.assert_call_count(url, 1)

    @responses.activate
    def test_getter_from_dict_twice_with_refresh_timer_updates_cache_once_with_json(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content 1"})
        responses.add(responses.GET, url, json={"key": "the content 2"})

        getter_file_content = {target: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)

            assert len(http_getter.scheduler.jobs) == 1
            assert http_getter.scheduler.jobs[0].interval == 1

            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            http_getter.scheduler.run_all()
            return_content_2 = http_getter.get_json()
            assert return_content_1 == {"key": "the content 1"}
            assert return_content_2 == {"key": "the content 2"}
            assert self._get_cache_as_json(http_getter) == return_content_2
            responses.assert_call_count(url, 2)

    @responses.activate
    def test_getter_from_dict_twice_with_refresh_timer_updates_cache_once_with_yaml(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content 1"})
        responses.add(responses.GET, url, json={"key": "the content 2"})

        getter_file_content = {target: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.yaml"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)

            assert len(http_getter.scheduler.jobs) == 1
            assert http_getter.scheduler.jobs[0].interval == 1

            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            http_getter.scheduler.run_all()
            return_content_2 = http_getter.get_json()
            assert return_content_1 == {"key": "the content 1"}
            assert return_content_2 == {"key": "the content 2"}
            assert self._get_cache_as_json(http_getter) == return_content_2
            responses.assert_call_count(url, 2)

    @responses.activate
    def test_getter_from_dict_three_times_with_refresh_timer_updates_cache_once(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content 1"})
        responses.add(responses.GET, url, json={"key": "the content 2"})
        responses.add(responses.GET, url, json={"key": "the content 3"})

        getter_file_content = {target: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert len(http_getter.scheduler.jobs) == 1
            assert http_getter.scheduler.jobs[0].interval == 1

            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            http_getter.scheduler.run_all()
            return_content_2 = http_getter.get_json()
            return_content_3 = http_getter.get_json()
            assert return_content_1 == {"key": "the content 1"}
            assert return_content_2 == {"key": "the content 2"}
            assert return_content_3 == {"key": "the content 2"}
            assert self._get_cache_as_json(http_getter) == return_content_2
            responses.assert_call_count(url, 2)

    @responses.activate
    def test_getter_from_dict_three_times_with_refresh_timer_updates_cache_twice(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content 1"})
        responses.add(responses.GET, url, json={"key": "the content 2"})
        responses.add(responses.GET, url, json={"key": "the content 3"})

        getter_file_content = {target: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert len(http_getter.scheduler.jobs) == 1
            assert http_getter.scheduler.jobs[0].interval == 1

            assert http_getter.cache is None
            return_content_1 = http_getter.get_json()
            http_getter.scheduler.run_all()
            return_content_2 = http_getter.get_json()
            http_getter.scheduler.run_all()
            return_content_3 = http_getter.get_json()
            assert return_content_1 == {"key": "the content 1"}
            assert return_content_2 == {"key": "the content 2"}
            assert return_content_3 == {"key": "the content 3"}
            assert self._get_cache_as_json(http_getter) == return_content_3
            responses.assert_call_count(url, 3)

    @responses.activate
    def test_getter_two_getters_with_different_urls_have_different_targets(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"

        target_2 = f"{uuid.uuid4()}/bar"
        url_2 = f"https://{target_2}"

        http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
        http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

        assert http_getter_1.target == target_1
        assert http_getter_2.target == target_2

    @responses.activate
    def test_getter_from_dict_with_two_getters_same_url_refresh_updates_cache(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(responses.GET, url, json={"key": "the content 1"})
        responses.add(responses.GET, url, json={"key": "the content 2"})

        getter_file_content = {target: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url)
            http_getter_2: HttpGetter = GetterFactory.from_string(url)

            assert len(http_getter_1.scheduler.jobs) == 1
            assert http_getter_1.scheduler.jobs[0].interval == 10

            assert http_getter_1.cache is None
            assert http_getter_2.cache is None

            return_content_1 = http_getter_1.get_json()
            http_getter_1.scheduler.run_all()
            return_content_2 = http_getter_2.get_json()

            assert self._get_cache_as_json(http_getter_1) == return_content_2
            assert self._get_cache_as_json(http_getter_2) == return_content_2

            assert return_content_1 == {"key": "the content 1"}
            assert return_content_2 == {"key": "the content 2"}

            responses.assert_call_count(url, 2)

    @responses.activate
    def test_getter_from_dict_with_two_getters_different_url_schedules_separately(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"
        responses.add(responses.GET, url_1, json={"key": "the content 1"})
        responses.add(responses.GET, url_1, json={"key": "the content 2"})

        target_2 = f"{uuid.uuid4()}/bar"
        url_2 = f"https://{target_2}"
        responses.add(responses.GET, url_2, json={"key": "the content 3"})
        responses.add(responses.GET, url_2, json={"key": "the content 4"})

        getter_file_content = {
            target_1: {"refresh_interval": 10},
            target_2: {"refresh_interval": 10},
        }
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
            http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

            assert http_getter_1.cache is None
            assert http_getter_2.cache is None

            return_content_1_1 = http_getter_1.get_json()
            assert self._get_cache_as_json(http_getter_1) == return_content_1_1
            http_getter_1.scheduler.run_all()
            return_content_1_2 = http_getter_1.get_json()
            assert self._get_cache_as_json(http_getter_1) == return_content_1_2

            return_content_2_1 = http_getter_2.get_json()
            assert self._get_cache_as_json(http_getter_2) == return_content_2_1
            http_getter_2.scheduler.run_all()
            return_content_2_2 = http_getter_2.get_json()
            assert self._get_cache_as_json(http_getter_2) == return_content_2_2

            assert return_content_1_1 == {"key": "the content 1"}
            assert return_content_1_2 == {"key": "the content 2"}
            assert return_content_2_1 == {"key": "the content 3"}
            assert return_content_2_2 == {"key": "the content 4"}

            responses.assert_call_count(url_1, 2)

    @responses.activate
    def test_getter_etags_with_same_target(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"
        responses.add(
            responses.GET,
            url,
            json={"key": "the content 1"},
            headers={"Content-Type": "application/json", "etag": "1"},
            status=200,
        )
        responses.add(responses.GET, url, headers={"etag": "1"}, status=304)
        responses.add(
            responses.GET,
            url,
            json={"key": "the content 2"},
            headers={"Content-Type": "application/json", "etag": "2"},
            status=200,
        )

        getter_file_content = {target: {"refresh_interval": 0}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert http_getter.etag is None
            response = http_getter.get_json()
            assert http_getter.etag == "1"
            assert response == {"key": "the content 1"}

            response = http_getter.get_json()
            assert http_getter.etag == "1"
            assert response == {"key": "the content 1"}

            response = http_getter.get_json()
            assert http_getter.etag == "2"
            assert response == {"key": "the content 2"}

    @responses.activate
    def test_getter_etags_with_different_targets(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"
        target_2 = f"{uuid.uuid4()}/bar"
        url_2 = f"https://{target_2}"

        config = {
            "json": {"key": "the content 1"},
            "headers": {"Content-Type": "application/json", "etag": "1"},
            "status": 200,
        }
        responses.add(responses.GET, url_1, **config)
        responses.add(responses.GET, url_2, **config)

        config = {"headers": {"etag": "1"}, "status": 304}
        responses.add(responses.GET, url_1, **config)
        responses.add(responses.GET, url_2, **config)

        config = {
            "json": {"key": "the content 2"},
            "headers": {"Content-Type": "application/json", "etag": "2"},
            "status": 200,
        }
        responses.add(responses.GET, url_1, **config)
        responses.add(responses.GET, url_2, **config)

        getter_file_content = {target_1: {"refresh_interval": 0}, target_2: {"refresh_interval": 0}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
            http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

            assert http_getter_1.etag is None
            assert http_getter_1.get_json() == {"key": "the content 1"}
            assert http_getter_1.etag == "1"

            assert http_getter_2.etag is None
            assert http_getter_2.get_json() == {"key": "the content 1"}
            assert http_getter_2.etag == "1"

            assert http_getter_1.get_json() == {"key": "the content 1"}
            assert http_getter_1.etag == "1"

            assert http_getter_2.get_json() == {"key": "the content 1"}
            assert http_getter_2.etag == "1"

            assert http_getter_1.get_json() == {"key": "the content 2"}
            assert http_getter_1.etag == "2"

            assert http_getter_2.get_json() == {"key": "the content 2"}
            assert http_getter_2.etag == "2"

    @responses.activate
    def test_getter_etags_with_refresh_interval(self, tmp_path):
        target = f"{uuid.uuid4()}/bar"
        url = f"https://{target}"

        responses.add(
            responses.GET,
            url,
            json={"key": "the content 1"},
            headers={"Content-Type": "application/json", "etag": "1"},
            status=200,
        )
        responses.add(responses.GET, url, headers={"etag": "1"}, status=304)
        responses.add(
            responses.GET,
            url,
            json={"key": "the content 2"},
            headers={"Content-Type": "application/json", "etag": "2"},
            status=200,
        )

        getter_file_content = {target: {"refresh_interval": 100}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter: HttpGetter = GetterFactory.from_string(url)
            assert http_getter.etag is None
            response = http_getter.get_json()
            assert http_getter.etag == "1"
            assert response == {"key": "the content 1"}

            response = http_getter.get_json()
            assert http_getter.etag == "1"
            assert response == {"key": "the content 1"}

            response = http_getter.get_json()
            assert http_getter.etag == "1"
            assert response == {"key": "the content 1"}

    @responses.activate
    def test_getter_with_parameters(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"
        responses.add(responses.GET, url_1, json={"key": "the content 1"})
        responses.add(responses.GET, url_1, json={"key": "the content 2"})

        target_2 = f"{uuid.uuid4()}/bar?foo=123&bar=asd"
        url_2 = f"https://{target_2}"
        responses.add(responses.GET, url_2, json={"key": "the content 3"})
        responses.add(responses.GET, url_2, json={"key": "the content 4"})

        getter_file_content = {
            target_1: {"refresh_interval": 10},
            target_2: {"refresh_interval": 10},
        }
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
            http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

            assert http_getter_1.cache is None
            assert http_getter_2.cache is None

            return_content_1_1 = http_getter_1.get_json()
            assert self._get_cache_as_json(http_getter_1) == return_content_1_1
            http_getter_1.scheduler.run_all()
            return_content_1_2 = http_getter_1.get_json()
            assert self._get_cache_as_json(http_getter_1) == return_content_1_2

            return_content_2_1 = http_getter_2.get_json()
            assert self._get_cache_as_json(http_getter_2) == return_content_2_1
            http_getter_2.scheduler.run_all()
            return_content_2_2 = http_getter_2.get_json()
            assert self._get_cache_as_json(http_getter_2) == return_content_2_2

            assert return_content_1_1 == {"key": "the content 1"}
            assert return_content_1_2 == {"key": "the content 2"}
            assert return_content_2_1 == {"key": "the content 3"}
            assert return_content_2_2 == {"key": "the content 4"}

            responses.assert_call_count(url_1, 2)

    @responses.activate
    def test_getter_refresh(self, tmp_path):
        target_ref_1 = f"{uuid.uuid4()}/bar"
        target_ref_2 = f"{uuid.uuid4()}/bar"
        target_no_ref = f"{uuid.uuid4()}/bar"
        url_ref_1 = f"https://{target_ref_1}"
        url_ref_2 = f"https://{target_ref_2}"
        url_no_ref_3 = f"https://{target_no_ref}"

        getter_file_content = {
            target_ref_1: {"refresh_interval": 10},
            target_ref_2: {"refresh_interval": 10},
            target_no_ref: {"refresh_interval": 0},
        }

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            GetterFactory.from_string(url_ref_1)
            GetterFactory.from_string(url_ref_1)
            GetterFactory.from_string(url_ref_2)
            GetterFactory.from_string(url_no_ref_3)
            GetterFactory.from_string("http://no_refresh")

            with mock.patch("logprep.util.getter.Scheduler.run_pending") as mock_run_pending:
                HttpGetter.refresh()
                assert mock_run_pending.call_count == 2

    @responses.activate
    def test_getter_callbacks(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"
        responses.add(responses.GET, url_1, json={"key": "the content 1"})
        responses.add(responses.GET, url_1, json={"key": "the content 2"})
        responses.add(responses.GET, url_1, json={"key": "the content 3"})

        target_2 = f"{uuid.uuid4()}/bar"
        url_2 = f"https://{target_2}"
        responses.add(responses.GET, url_2, json={"key": "the content 4"})
        responses.add(responses.GET, url_2, json={"key": "the content 5"})

        getter_file_content = {
            target_1: {"refresh_interval": 10},
            target_2: {"refresh_interval": 10}
        }
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
            http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

            self._callback_value = 0

            def callback(foo, bar, keyword1=0):
                self._callback_value += foo + bar + keyword1

            http_getter_1.add_callback(callback, 1, 2, keyword1=3)

            http_getter_1.get_json()
            assert self._callback_value == 0
            http_getter_1.scheduler.run_all()
            assert self._callback_value == 6
            http_getter_1.get_json()
            assert self._callback_value == 6
            http_getter_1.scheduler.run_all()
            http_getter_1.get_json()
            assert self._callback_value == 12

            http_getter_2.get_json()
            assert self._callback_value == 12
            http_getter_2.scheduler.run_all()
            http_getter_2.get_json()
            assert self._callback_value == 12
            http_getter_2.add_callback(callback, 1, 0, keyword1=1)
            http_getter_2.scheduler.run_all()
            http_getter_2.get_json()
            assert self._callback_value == 14

    @responses.activate
    def test_getter_callbacks_for_target(self, tmp_path):
        target_1 = f"{uuid.uuid4()}/bar"
        url_1 = f"https://{target_1}"
        responses.add(responses.GET, url_1, json={"key": "the content 1"})
        responses.add(responses.GET, url_1, json={"key": "the content 2"})
        responses.add(responses.GET, url_1, json={"key": "the content 3"})

        target_2 = f"{uuid.uuid4()}/bar"
        url_2 = f"https://{target_2}"
        responses.add(responses.GET, url_2, json={"key": "the content 4"})
        responses.add(responses.GET, url_2, json={"key": "the content 5"})

        getter_file_content = {
            target_1: {"refresh_interval": 10},
            target_2: {"refresh_interval": 10}
        }
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            http_getter_1: HttpGetter = GetterFactory.from_string(url_1)
            http_getter_2: HttpGetter = GetterFactory.from_string(url_2)

            self._callback_value = 0

            def callback(foo, bar, keyword1=0):
                self._callback_value += foo + bar + keyword1

            HttpGetter.add_callback_for_target(target_1, callback, 1, 2, keyword1=3)

            http_getter_1.get_json()
            assert self._callback_value == 0
            http_getter_1.scheduler.run_all()
            assert self._callback_value == 6
            http_getter_1.get_json()
            assert self._callback_value == 6
            http_getter_1.scheduler.run_all()
            http_getter_1.get_json()
            assert self._callback_value == 12

            http_getter_2.get_json()
            assert self._callback_value == 12
            http_getter_2.scheduler.run_all()
            http_getter_2.get_json()
            assert self._callback_value == 12
            HttpGetter.add_callback_for_target(target_2, callback, 1, 0, keyword1=1)
            http_getter_2.scheduler.run_all()
            http_getter_2.get_json()
            assert self._callback_value == 14

    @staticmethod
    def _get_cache_as_json(http_getter: HttpGetter) -> dict:
        return json.loads(http_getter.cache.decode())
