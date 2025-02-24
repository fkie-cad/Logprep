# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from unittest import mock

import pytest

from logprep.generator.http.sender import Sender  # Adjust import as needed


class TestSender:
    def setup_method(self):
        self.mock_batcher = mock.MagicMock()
        self.mock_output = mock.MagicMock()
        self.sender = Sender(
            self.mock_batcher, self.mock_output, **{"target_url": "http://example.com"}
        )

    def test_init(self):
        assert self.sender.batcher is self.mock_batcher
        assert self.sender.output is self.mock_output

    def test_init_raises_no_target_url(self):
        with pytest.raises(ValueError):
            Sender(self.mock_batcher, self.mock_output)

    def test_send_batch_calls_store(self):
        self.mock_batcher.batches = [["file1.txt", "file2.txt"], ["file3.txt"]]
        expected_calls = [
            mock.call("http://example.com/file1.txt"),
            mock.call("http://example.com/file2.txt"),
            mock.call("http://example.com/file3.txt"),
        ]
        self.sender.send_batches()
        self.mock_output.store.assert_has_calls(expected_calls, any_order=False)
        assert self.mock_output.store.call_count == 3
