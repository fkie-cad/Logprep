# pylint: disable=missing-docstring
# pylint: disable=protected-access
from datetime import datetime, timedelta
from unittest import mock

import pytest
import responses
from requests import Session
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
        assert test._refresh_token == "refresh_token123123"
        assert test._expiry_time == expected_expiry_time

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
        mock_now = datetime.now()
        test._refresh_token = "refresh1234"
        test._expiry_time = mock_now  # expire the token
        # end prepare mock
        session = test.get_session()
        assert session.headers.get("Authorization") == "Bearer new toooken", "new should be used"
        assert test._refresh_token == "refresh_token123123", "new refresh token should be set"
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
        test._expiry_time = mock_now  # expire the token
        new_session = test.get_session()
        assert new_session is not session, "new session should be returned for every refresh"

    def test_get_session_does_not_refresh_token_if_not_expired(self):
        test = OAuth2PasswordFlowCredentials(
            endpoint="https://the.endpoint",
            password="password",
            username="user",
        )
        test._refresh_token = "refresh1234"
        test._expiry_time = datetime.now() + timedelta(seconds=3600)
        test._session = Session()
        test._session.headers.update({"Authorization": "Bearer bla"})
        session = test.get_session()


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
