# pylint: disable=missing-docstring
# pylint: disable=protected-access
import re
from datetime import datetime, timedelta
from unittest import mock

import pytest
import requests
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
    CredentialsFileSchema,
    MTLSCredentials,
    OAuth2ClientFlowCredentials,
    OAuth2PasswordFlowCredentials,
    OAuth2TokenCredentials,
)
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE


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
                "valid token",
                {"token": "hioinnjdijskjdhfue672534kmsdk"},
                None,
                None,
            ),
        ],
    )
    def test_init(self, testcase, kwargs, error, error_message):
        if error is None:
            _ = OAuth2TokenCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                _ = OAuth2TokenCredentials(**kwargs)

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
            (
                "valid with client credentials",
                {
                    "endpoint": "https://some.endpoint/endpoint",
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                    "client_id": "client_id",
                    "client_secret": "client_secret",
                },
                None,
                None,
            ),
        ],
    )
    def test_init(self, testcase, error, kwargs, error_message):
        if error is None:
            _ = OAuth2PasswordFlowCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                _ = OAuth2PasswordFlowCredentials(**kwargs)

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
    def test_get_session_returns_session_with_token(self):
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
    def test_get_session_returns_session_with_token_and_uses_client_creds(self):
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
                matchers.header_matcher(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ=",
                    }
                ),
            ],
        )
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
            client_id="client_id",
            client_secret="client_secret",
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
            _ = OAuth2ClientFlowCredentials(**kwargs)
        else:
            with pytest.raises(error, match=error_message):
                _ = OAuth2ClientFlowCredentials(**kwargs)

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

    @responses.activate
    def test_get_session_error_handling_for_status_code_not_400(self):
        test = OAuth2ClientFlowCredentials(
            endpoint="https://the.endpoint",
            client_secret="very secret password",
            client_id="allmighty_client_id",
        )
        responses.add(
            responses.POST,
            "https://the.endpoint",
            json={
                "error": "this is a custom application error",
            },
            status=503,
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
        error_message = r"Service Unavailable for url"
        with pytest.raises(requests.HTTPError, match=error_message):
            _ = test.get_session()


class TestCredentialsFactory:

    @pytest.mark.parametrize(
        "testcase, credential_file_content, instance, error",
        [
            (
                "Return BasicAuthCredential object",
                """---
getter:
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
getter:
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
getter:
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
getter:
    "https://some.url":
        token: "jsoskdmoiewjdoeijkxsmoiqw8jdiowd0"
""",
                OAuth2TokenCredentials,
                None,
            ),
            (
                "Return None if credentials are missing",
                """---
getter:
    "https://some.url":
""",
                type(None),
                None,
            ),
            (
                "Return None if wrong URL is given",
                """---
getter:             
    "https://some.other.url":
        token: "jsoskdmoiewjdoeijkxsmoiqw8jdiowd0"
""",
                type(None),
                None,
            ),
            (
                "Raises InvalidConfigurationError credentials file is invalid yml",
                """---
getter:                
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
"getter": {
    "https://some.url": {
        "endpoint": "https://endpoint.end",
        "client_id": "test",
        "client_secret": "test"
        }
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
"getter": {
    "https://some.url": 
        "endpoint": "https://endpoint.end",
        "client_id": "test",
        "client_secret": "test"
""",
                None,
                InvalidConfigurationError,
            ),
            (
                "Return OAuth2PassowordFlowCredentials object with extra client_id",
                """---
getter:
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
                "Return OAuthTokenCredential object when other params are given",
                """---
getter:
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
getter:
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
getter:
    "https://some.url":
        endpoint: https://endpoint.end
        client_id: test
        username: test
        password: test
        client_secret: test
""",
                OAuth2PasswordFlowCredentials,
                None,
            ),
            (
                "Return None if no matching credentials class is found",
                """---
getter:
    "https://some.url":
        endpoint: https://endpoint.end
        username: test
        client_secret: test
""",
                type(None),
                None,
            ),
            (
                "Error",
                """---
getter:
    "https://some.url":
        endpoint: https://endpoint.end
        username: test
        password:
""",
                type(None),
                InvalidConfigurationError,
            ),
            (
                "Return MTLSCredentials object if certificate and key are given",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
        cert: "path/to/cert"
""",
                MTLSCredentials,
                None,
            ),
            (
                "Return MTLSCredentials object if certificate key and ca cert are given",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
        cert: "path/to/cert"
        ca_cert: "path/to/ca/cert"
        endpoint: https://endpoint.end
        client_id: test
        username: test
        password: test
        client_secret: test
""",
                MTLSCredentials,
                None,
            ),
            (
                "Return MTLSCredentials object if cert key and ca cert are given with extra params",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
        cert: "path/to/cert"
        ca_cert: "path/to/ca/cert"
""",
                MTLSCredentials,
                None,
            ),
            (
                "Return MTLSCredentials object if cert and key are given with extra parameters",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
        cert: "path/to/cert"
        endpoint: https://endpoint.end
        username: test
""",
                MTLSCredentials,
                None,
            ),
            (
                "Return None if certificate is missing",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
""",
                type(None),
                None,
            ),
            (
                "Return InvalidConfigurationError object if certificate is empty",
                """---
getter:
    "https://some.url":
        client_key: "path/to/client/key"
        cert: 
""",
                None,
                InvalidConfigurationError,
            ),
        ],
    )
    def test_getter_credentials_returns_expected_credential_object(
        self, testcase, credential_file_content, instance, tmp_path, error
    ):
        credential_file_path = tmp_path / "credentials"
        credential_file_path.write_text(credential_file_content)
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            if error is not None:
                with pytest.raises(error):
                    creds = CredentialsFactory.from_target("https://some.url/configuration")
            else:
                creds = CredentialsFactory.from_target("https://some.url/configuration")
                assert isinstance(creds, instance), testcase

    def test_input_credentials_returns_expected_credentials_object(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
input:
    endpoints:
        /some/auth/endpoint:
            username: test_user
            password: myverysecretpassword
"""
        )
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_endpoint("/some/auth/endpoint")
            assert isinstance(creds, BasicAuthCredentials)
            assert "test_user" in creds.username

    def test_credentials_returns_none_if_env_not_set(self):
        creds = CredentialsFactory.from_target("https://some.url/configuration")
        assert creds is None

    def test_credentials_from_root_url(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
getter:
    "http://some.url":
        endpoint: https://endpoint.end
        client_id: test
        client_secret: test
"""
        )
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_target("http://some.url")
            assert isinstance(creds, OAuth2ClientFlowCredentials)

    def test_credentials_is_none_on_invalid_credentials_file_path(self):
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: "this is something useless"}
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
                "Return BasicAuthCredential object with no endpoint and password_file",
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
getter:
    "http://some.url":
        {endpoint}
        username: testuser
        client_id: testid
        {type_of_secret}: {secret_file_path}
"""
        )
        secret_file_path.write_text(secret_content)
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_target("http://some.url/configuration")
            assert isinstance(creds, instance), testcase

    def test_credentials_reads_secret_file_content_from_every_given_file(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        secret_file_path_0 = tmp_path / "secret-0.txt"
        secret_file_path_1 = tmp_path / "secret-1.txt"

        credential_file_path.write_text(
            f"""---
getter:
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

        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            creds = CredentialsFactory.from_target("http://some.url/configuration")
            assert isinstance(creds, Credentials)

    @mock.patch.object(CredentialsFactory, "_logger")
    def test_warning_logged_when_extra_params_given(self, mock_logger):
        credentials_file_content_with_extra_params = {
            "endpoint": "https://endpoint.end",
            "client_id": "test",
            "client_secret": "test",
            "username": "user1",
            "password": "password",
            "extra_param": "extra",
        }
        _ = CredentialsFactory.from_dict(credentials_file_content_with_extra_params)
        mock_logger.warning.assert_called_once()
        assert re.search(
            r"OAuth password authorization for confidential clients",
            mock_logger.mock_calls[0][1][0],
        )

    def test_from_target_raises_when_getter_key_not_set(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
    "http://some.url":
        endpoint: "https://endpoint.end"
        username: testuser
        password_file: "thisismysecretsecretclientsecret"
"""
        )
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            with pytest.raises(
                InvalidConfigurationError,
                match="Invalid credentials file.* unexpected keyword argument 'http://some.url'",
            ):
                creds = CredentialsFactory.from_target("http://some.url/configuration")
                assert isinstance(creds, InvalidConfigurationError)

    def test_from_endpoint_raises_when_input_key_not_set(self, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
    /some/endpoint:
        username: testuser
        password_file: "thisismysecretsecretclientsecret"
"""
        )
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            with pytest.raises(
                InvalidConfigurationError,
                match="Invalid credentials file.* unexpected keyword argument '/some/endpoint'",
            ):
                creds = CredentialsFactory.from_endpoint("/some/endpoint")
                assert isinstance(creds, InvalidConfigurationError)


class TestMTLSCredentials:
    def test_get_session_returns_session_and_cert_is_set(self):
        test = MTLSCredentials(
            cert="path/to/cert",
            client_key="path/to/key",
        )
        assert test.get_session() is not None
        assert test._session.cert is not None

    def test_get_session_sets_ca_cert_for_verification(self):
        test = MTLSCredentials(
            cert="path/to/cert",
            client_key="path/to/key",
            ca_cert="path/to/ca/cert",
        )
        assert test.get_session() is not None
        assert "path/to/cert" in test._session.cert
        assert "path/to/key" in test._session.cert
        assert "path/to/ca/cert" in test._session.verify


class TestCredentialsFileSchema:
    def test_credential_file_can_be_instanciated(self):
        credentials_file_content = {
            "input": {
                "endpoints": {
                    "some/endpoint": {
                        "username": "user1",
                        "password": "password",
                    }
                }
            },
            "getter": {
                "some/endpoint": {
                    "username": "user1",
                    "password": "password",
                }
            },
        }
        creds = CredentialsFileSchema(**credentials_file_content)
        assert isinstance(creds, CredentialsFileSchema)
