# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
from unittest import mock

import pytest
from logprep.abc.input import CriticalInputError
from tests.unit.connector.base import BaseInputTestCase


class TestJsonlInput(BaseInputTestCase):
    timeout = 0.1

    CONFIG = {"type": "jsonl_input", "documents_path": "/does/not/matter"}

    parse_function = "logprep.connector.jsonl.input.parse_jsonl"

    @mock.patch(parse_function)
    def test_documents_returns(self, mock_parse):
        return_value = [{"message": "test_message"}]
        mock_parse.return_value = return_value
        assert self.object._documents == return_value

    @mock.patch(parse_function)
    def test_get_next_returns_document(self, mock_parse):
        mock_parse.return_value = [{"message": "test_message"}]
        expected = {"message": "test_message"}
        document, _ = self.object.get_next(self.timeout)
        assert document == expected

    @mock.patch(parse_function)
    def test_get_next_returns_multiple_documents(self, mock_parse):
        mock_parse.return_value = [{"order": 0}, {"order": 1}]
        assert ({"order": 0}, None) == self.object.get_next(self.timeout)
        assert ({"order": 1}, None) == self.object.get_next(self.timeout)

    @mock.patch(parse_function)
    def test_raises_exception_if_not_a_dict(self, mock_parse):
        mock_parse.return_value = ["no dict"]
        with pytest.raises(CriticalInputError, match=r"not a dict"):
            _ = self.object.get_next(self.timeout)

    @mock.patch(parse_function)
    def test_raises_exception_if_one_element_is_not_a_dict(self, mock_parse):
        mock_parse.return_value = [{"order": 0}, "not a dict", {"order": 1}]
        with pytest.raises(CriticalInputError, match=r"not a dict"):
            _ = self.object.get_next(self.timeout)
            _ = self.object.get_next(self.timeout)
            _ = self.object.get_next(self.timeout)
