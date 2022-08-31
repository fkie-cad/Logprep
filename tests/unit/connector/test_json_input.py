# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import json
from unittest import mock

import pytest
from logprep.input.input import CriticalInputError
from logprep.input.json_input import JsonInput


class DummyError(BaseException):
    pass


class TestJsonInput:
    timeout = 0.1

    def create_input(self, documents: str) -> None:
        mock_open = mock.mock_open(read_data=json.dumps(documents))
        with mock.patch("builtins.open", mock_open):
            self.input = JsonInput("")

    def test_get_next_returns_document(self):
        expected = {"message": "test_message"}
        self.create_input(expected)
        document = self.input.get_next(self.timeout)
        assert document == expected

    def test_get_next_returns_multiple_documents(self):
        documents = [{"order": 0}, {"order": 1}]
        self.create_input(documents)
        assert {"order": 0} == self.input.get_next(self.timeout)
        assert {"order": 1} == self.input.get_next(self.timeout)

    def test_raises_exception_if_not_a_dict(self):
        documents = ["no dict"]
        self.create_input(documents)
        with pytest.raises(CriticalInputError, match=r"not a dict"):
            _ = self.input.get_next(self.timeout)
