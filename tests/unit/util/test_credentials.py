# pylint: disable=missing-docstring
import pytest

from logprep.util.credentials import BasicAuthCredentials


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
