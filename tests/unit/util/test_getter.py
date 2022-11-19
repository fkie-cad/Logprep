# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import json
import requests
from pathlib import Path
import re
import pytest
from ruamel.yaml import YAML
from unittest import mock
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
        http_getter = GetterFactory.from_string(
            "https://raw.githubusercontent.com/fkie-cad/Logprep/main/tests/testdata/config/config.yml"
        )
        resp_text = Path("tests/testdata/config/config.yml").read_text()
        with mock.patch("requests.get") as mock_request_get:
            mock_request_get.return_value.text = resp_text
            http_getter.get()
            assert "headers" in mock_request_get.call_args.kwargs
            user_agent = mock_request_get.call_args.kwargs.get("headers").get("User-Agent")
            assert re.search(r"Logprep version \d+", user_agent)

    def test_provides_oauth_compliant_headers(self):
        http_getter = GetterFactory.from_string(
            "https://oauth:ajhsdfpoweiurjdfs239487@the.target.url/targetfile"
        )
        with mock.patch("requests.get") as mock_request_get:
            http_getter.get()
            assert "headers" in mock_request_get.call_args.kwargs
            headers = mock_request_get.call_args.kwargs.get("headers")
            assert headers.get("Authorization") == "Bearer ajhsdfpoweiurjdfs239487"
            assert mock_request_get.call_args.kwargs.get("auth") is None
            assert (
                mock_request_get.call_args.kwargs.get("url") == "https://the.target.url/targetfile"
            )

    def test_provides_basic_authentication(self):
        http_getter = GetterFactory.from_string(
            "https://myusername:mypassword@the.target.url/targetfile"
        )
        with mock.patch("requests.get") as mock_request_get:
            http_getter.get()
            assert "auth" in mock_request_get.call_args.kwargs
            auth_info = mock_request_get.call_args.kwargs.get("auth")
            assert auth_info.username == "myusername"
            assert auth_info.password == "mypassword"
            assert (
                mock_request_get.call_args.kwargs.get("url") == "https://the.target.url/targetfile"
            )
