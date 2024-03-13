# pylint: disable=missing-docstring
# pylint: disable=protected-access
from datetime import datetime, timedelta
from unittest import mock

import pytest
import responses
from requests import Session
from responses import matchers

from logprep.factory_error import InvalidConfigurationError
from logprep.util.credentials import (
    AccessToken,
    BasicAuthCredentials,
    Credentials,
    CredentialsBadRequestError,
    CredentialsFactory,
    OAuth2ClientFlowCredentials,
    OAuth2PasswordFlowCredentials,
    OAuth2TokenCredentials,
)


class TestBasicAuthCredentials:

    @pytest.mark.parametrize(
        "testcase, kwargs, error, error_message",
        [
            (
                "invalid because no kwargs",
                {},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "invalid because username is not a string",
                {"username": 123, "password": "password"},
                TypeError,
                r"must be <class \'str\'>",
            ),
            (
                "invalid because password is missing",
                {"username": "user"},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "valid",
                {"username": "user", "password": "password"},
                None,
                None,
            ),
            (
                "invalid, because password not a string",
                {"username": "user", "password": 1.2},
                TypeError,
                r"must be <class \'str\'>",
            ),
        ],
    )
    def test_init(self, testcase, kwargs, error, error_message):
        if error is None:
            _ = BasicAuthCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                _ = BasicAuthCredentials(**kwargs)

    def test_get_session_returns_session(self):
        test = BasicAuthCredentials(username="user", password="password")
        assert test.get_session() is not None

    def test_get_session_returns_session_with_auth(self):
        test = BasicAuthCredentials(username="user", password="password")
        session = test.get_session()
        assert session.auth == ("user", "password")


class TestOAuth2TokenCredentials:

    @pytest.mark.parametrize(
        "testcase, kwargs, error, error_message",
        [
            (
                "invalid because no kwargs",
                {},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "invalid because token is not a string",
                {"token": 216742},
                TypeError,
                r"must be <class 'str'>",
            ),
            (
                "valdi token",
                {"token": "hioinnjdijskjdhfue672534kmsdk"},
                None,
                None,
            ),
        ],
    )
    def test_init(self, testcase, kwargs, error, error_message):
        if error is None:
            test = OAuth2TokenCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                test = OAuth2TokenCredentials(**kwargs)

    def test_get_session_returns_session(self):
        test = OAuth2TokenCredentials(token="tooooooken")
        assert test.get_session() is not None

    def test_get_session_returns_session_with_auth(self):
        test = OAuth2TokenCredentials(token="tooooooken")
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer tooooooken"


class TestOAuth2PasswordFlowCredentials:

    @pytest.mark.parametrize(
        "testcase, kwargs, error, error_message",
        [
            (
                "invalid because no kwargs",
                {},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "invalid because kwarg is not string",
                {
                    "endpoint": 12345,
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                },
                TypeError,
                r"must be <class 'str'>",
            ),
            (
                "invalid because one kwarg is missing",
                {
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                },
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "valid",
                {
                    "endpoint": "https://some.endpoint/endpoint",
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                },
                None,
                None,
            ),
            (
                "valid with optional timeout",
                {
                    "endpoint": "https://some.endpoint/endpoint",
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                    "timeout": 123,
                },
                None,
                None,
            ),
            (
                "invalid with refresh token",
                {
                    "endpoint": "https://some.endpoint/endpoint",
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                    "refresh_token": "refresh_token",
                },
                TypeError,
                r"got an unexpected keyword argument 'refresh_token'",
            ),
            (
                "invalid with expiry time",
                {
                    "endpoint": "https://some.endpoint/endpoint",
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                    "expiry_time": "2022-12-12 12:12:12",
                },
                TypeError,
                r"got an unexpected keyword argument 'expiry_time'",
            ),
        ],
    )
    def test_init(self, testcase, error, kwargs, error_message):
        if error is None:
            test = OAuth2PasswordFlowCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                test = OAuth2PasswordFlowCredentials(**kwargs)

    @responses.activate
    def test_get_session_returns_session(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={"access_token": "toooooken"},
        )
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        assert test.get_session() is not None

    @responses.activate
    def test_get_session_returns_session_with_auth(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "password",
                        "username": "user",
                        "password": "password",
                    }
                ),
                matchers.header_matcher({"Content-Type": "application/x-www-form-urlencoded"}),
            ],
        )
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer toooooken"

    @responses.activate
    def test_get_session_sets_refresh_token_and_expiry_time(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "password",
                        "username": "user",
                        "password": "password",
                    }
                ),
                matchers.header_matcher({"Content-Type": "application/x-www-form-urlencoded"}),
            ],
        )
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        mock_now = datetime.now()
        expected_expiry_time = mock_now + timedelta(seconds=3600)
        with mock.patch("logprep.util.credentials.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_now
            session = test.get_session()
        assert session.headers.get("Authorization").startswith("Bearer")
        assert test._token.refresh_token == "refresh_token123123"
        assert test._token.expiry_time == expected_expiry_time

    @responses.activate
    def test_get_session_uses_refresh_token_if_token_is_expired(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "new toooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": "refresh1234",
                    }
                ),
                matchers.header_matcher({"Content-Type": "application/x-www-form-urlencoded"}),
            ],
        )
        # start prepare mock state after getting first authorization token
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        test._session = Session()
        test._session.headers.update({"Authorization": "Bearer bla"})
        test._token = AccessToken(
            token="doesnotmatter", refresh_token="refresh1234", expires_in=3600
        )
        mock_expiry_time = datetime.now() - timedelta(seconds=3600)
        test._token.expiry_time = mock_expiry_time  # expire the token
        # end prepare mock
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer new toooken", "new should be used"
        assert test._token.refresh_token == "refresh_token123123", "new refresh token should be set"
        # next refresh with new refresh token
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "very new token",
                "expires_in": 3600,
                "refresh_token": "next_refresh_token",
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": "refresh_token123123",
                    }
                ),
                matchers.header_matcher({"Content-Type": "application/x-www-form-urlencoded"}),
            ],
        )
        test._token.expiry_time = mock_expiry_time  # expire the token
        new_session = test.get_session()
        assert new_session is not session, "new session should be returned for every refresh"

    @responses.activate
    def test_get_session_does_not_refresh_token_if_not_expired(self):
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        test._token = AccessToken(token="bla", refresh_token="refresh1234", expires_in=3600)
        test._session = Session()
        test._session.headers.update({"Authorization": "Bearer bla"})
        session = test.get_session()  # should not lead to an exception
        assert session

    @pytest.mark.parametrize(
        "error_reason",
        [
            "invalid_request",
            "invalid_client",
            "invalid_grant",
            "unauthorized_client",
            "unsupported_grant_type",
        ],
    )
    @responses.activate
    def test_get_session_error_handling(self, error_reason):
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            username="user",
            password="password",
        )
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "error": error_reason,
            },
            status=400,
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "password",
                        "username": "user",
                        "password": "password",
                    }
                ),
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                    }
                ),
            ],
        )
        error_message = rf"Authentication failed with status code 400 Bad Request: {error_reason}"
        with pytest.raises(CredentialsBadRequestError, match=error_message):
            _ = test.get_session()


class TestOAuth2ClientFlowCredentials:

    @pytest.mark.parametrize(
        "testcase, kwargs, error, error_message",
        [
            (
                "invalid because no kwargs",
                {},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "invalid because kwargs missing",
                {"endpoint": "https://some.url/endpoint", "client_id": "test_id"},
                TypeError,
                r"missing \d required keyword-only argument",
            ),
            (
                "invalid because invalid kwarg",
                {
                    "endpoint": "https://some.url/endpoint",
                    "client_id": "some_id",
                    "client_secret": 1253.67484,
                },
                TypeError,
                r"must be <class 'str'>",
            ),
            (
                "valid",
                {
                    "endpoint": "https://some.url/endpoint",
                    "client_id": "some_id",
                    "client_secret": "hijijsmmakaksjasd",
                },
                None,
                None,
            ),
        ],
    )
    def test_init(self, testcase, kwargs, error, error_message):
        if error is None:
            test = OAuth2ClientFlowCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                test = OAuth2ClientFlowCredentials(**kwargs)

    @responses.activate
    def test_get_session_returns_session(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={"access_token": "toooooken"},
        )
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        assert test.get_session() is not None

    @responses.activate
    def test_get_session_returns_session_with_auth(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "toooooken",
                "expires_in": 3600,
                "refresh_token": "refresh_token123123",
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "client_credentials",
                    }
                ),
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic YWxsbWlnaHR5X2NsaWVudF9pZDp2ZXJ5IHNlY3JldCBwYXNzd29yZA==",
                    }
                ),
            ],
        )
        test = OAuth2ClientFlowCredentials(
            endpoint="https://the.endpoint",
            client_secret="very secret password",
            client_id="allmighty_client_id",
        )
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer toooooken"

    @responses.activate
    def test_get_session_does_not_requests_new_token_if_not_expired(self):
        test = OAuth2ClientFlowCredentials(
            endpoint="https://the.endpoint",
            client_secret="very secret password",
            client_id="allmighty_client_id",
        )
        test._token = AccessToken(token="bla", expires_in=3600)
        test._session = Session()
        test._session.headers.update({"Authorization": "Bearer bla"})
        session = test.get_session(), "should not raise"
        assert session

    @responses.activate
    def test_get_session_refreshes_token(self):
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "new toooken",
                "expires_in": 3600,
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "client_credentials",
                    }
                ),
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic YWxsbWlnaHR5X2NsaWVudF9pZDp2ZXJ5IHNlY3JldCBwYXNzd29yZA==",
                    }
                ),
            ],
        )
        # start prepare mock state after getting first authorization token
        test = OAuth2ClientFlowCredentials(
            endpoint="https://the.endpoint",
            client_secret="very secret password",
            client_id="allmighty_client_id",
        )
        test._session = Session()
        test._session.headers.update({"Authorization": "Bearer bla"})
        test._token = AccessToken(token="doesnotmatter", expires_in=3600)
        mock_expiry_time = datetime.now() - timedelta(seconds=3600)
        test._token.expiry_time = mock_expiry_time  # expire the token
        # end prepare mock
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer new toooken", "new should be used"
        # next refresh with new refresh token
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "access_token": "very new token",
                "expires_in": 3600,
            },
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "client_credentials",
                    }
                ),
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic YWxsbWlnaHR5X2NsaWVudF9pZDp2ZXJ5IHNlY3JldCBwYXNzd29yZA==",
                    }
                ),
            ],
        )
        test._token.expiry_time = mock_expiry_time  # expire the token
        new_session = test.get_session()
        assert new_session is not session, "new session should be returned for every refresh"

    @pytest.mark.parametrize(
        "error_reason",
        [
            "invalid_request",
            "invalid_client",
            "invalid_grant",
            "unauthorized_client",
            "unsupported_grant_type",
        ],
    )
    @responses.activate
    def test_get_session_error_handling(self, error_reason):
        test = OAuth2ClientFlowCredentials(
            endpoint="https://the.endpoint",
            client_secret="very secret password",
            client_id="allmighty_client_id",
        )
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "error": error_reason,
            },
            status=400,
            match=[
                matchers.urlencoded_params_matcher(
                    {
                        "grant_type": "client_credentials",
                    }
                ),
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic YWxsbWlnaHR5X2NsaWVudF9pZDp2ZXJ5IHNlY3JldCBwYXNzd29yZA==",
                    }
                ),
            ],
        )
        error_message = rf"Authentication failed with status code 400 Bad Request: {error_reason}"
        with pytest.raises(CredentialsBadRequestError, match=error_message):
            _ = test.get_session()


class TestCredentialsFactory:

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
            if error is not None:
                with pytest.raises(error):
                    creds = CredentialsFactory.from_target("https://some.url/configuration")
            else:
                creds = CredentialsFactory.from_target("https://some.url/configuration")
                assert isinstance(creds, instance), testcase

    def test_credentials_returns_none_if_env_not_set(self):
        creds = CredentialsFactory.from_target("https://some.url/configuration")
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
            creds = CredentialsFactory.from_target("http://some.url")
            assert isinstance(creds, OAuth2ClientFlowCredentials)

    def test_credentials_is_none_on_invalid_credentials_file_path(self):
        mock_env = {"LOGPREP_CREDENTIALS_FILE": "this is something useless"}
        with mock.patch.dict("os.environ", mock_env):
            with pytest.raises(InvalidConfigurationError, match=r"wrong credentials file path"):
                creds = CredentialsFactory.from_target("https://some.url")
                assert creds is None

    @pytest.mark.parametrize(
        "testcase, type_of_secret, endpoint, secret_content, instance",
        [
            (
                "Return OAuthPasswordFlowCredential object when password file is given",
                "password_file",
                "endpoint: https://endpoint.end",
                "hiansdnjskwuthisisaverysecretsecret",
                OAuth2PasswordFlowCredentials,
            ),
            (
                "Return OAuthClientFlowCredentials object when client secret file is given",
                "client_secret_file",
                "endpoint: https://endpoint.end",
                "hiansdnjskwuthisisaverysecretsecret",
                OAuth2ClientFlowCredentials,
            ),
            (
                "Return OAuthTokenCredential object when token file is given",
                "token_file",
                "endpoint: https://endpoint.end",
                "hiansdnjskwuthisisaverysecretsecret",
                OAuth2TokenCredentials,
            ),
            (
                "Return BasicAuthCredential object when no endpoint is given and password_file is given",
                "password_file",
                "",
                "hiansdnjskwuthisisaverysecretsecret",
                BasicAuthCredentials,
            ),
        ],
    )
    def test_credentials_reads_secret_file_content(
        self, tmp_path, testcase, type_of_secret, endpoint, secret_content, instance
    ):
        credential_file_path = tmp_path / "credentials.yml"
        secret_file_path = tmp_path / "secret.txt"
        credential_file_path.write_text(
            f"""---
"http://some.url":
    {endpoint}
    username: testuser
    client_id: testid
    {type_of_secret}: {secret_file_path}
"""
        )
        secret_file_path.write_text(secret_content)
        mock_env = {"LOGPREP_CREDENTIALS_FILE": str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_target("http://some.url/configuration")
            assert isinstance(creds, instance), testcase

    def test_credentials_reads_secret_file_content_from_every_given_file(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        secret_file_path_0 = tmp_path / "secret-0.txt"
        secret_file_path_1 = tmp_path / "secret-1.txt"

        credential_file_path.write_text(
            f"""---
"http://some.url":
    endpoint: "https://endpoint.end"
    username: testuser
    client_id: testid
    client_secret_file: {secret_file_path_0}
    password_file: {secret_file_path_1}
"""
        )
        secret_file_path_0.write_text("thisismysecretsecretclientsecret")
        secret_file_path_1.write_text("thisismysecorndsecretsecretpasswordsecret")

        mock_env = {"LOGPREP_CREDENTIALS_FILE": str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_target("http://some.url/configuration")
            assert isinstance(creds, Credentials)
