# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from unittest import mock

from logprep.generator.sender import Sender  # Adjust import as needed


class TestSender:
    def setup_method(self):
        self.mock_input_events = [["file1.txt", "file2.txt"], ["file3.txt"]]
        self.mock_output = mock.MagicMock()
        self.sender = Sender(
            self.mock_input_events, self.mock_output, **{"target_url": "http://example.com"}
        )

    def test_init_sets_dafault(self):
        assert self.sender.output is self.mock_output
        assert self.sender.thread_count is 1

    def test_init_overwrites_default(self):
        self.sender = Sender(
            self.mock_input_events,
            self.mock_output,
            **{"target_url": "http://example.com", "thread_count": 2},
        )
        assert self.sender.thread_count == 2

    def test_send_batch_calls_store(self):
        expected_calls = [
            mock.call(["file1.txt", "file2.txt"]),
            mock.call(["file3.txt"]),
        ]
        self.sender.send_batches()
        self.mock_output.store.assert_has_calls(expected_calls, any_order=False)
        assert self.mock_output.store.call_count == 2
