# pylint: disable=missing-docstring
import pytest

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
                    "grand_type": 23.78,
                    "password": "hskwmksölkpwksmksksksmk",
                    "username": "test_user",
                },
                TypeError,
                r"must be <class 'str'>",
            ),
            (
                "invalid because one kwarg is missing",
                {
                    "grand_type": "client",
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
                    "grand_type": "client",
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
                "invalid because one kwarg is missing",
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
