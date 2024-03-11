# pylint: disable=missing-docstring
import pytest
import responses
from responses import matchers

from logprep.util.credentials import (
    BasicAuthCredentials,
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
