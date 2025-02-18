# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from unittest import mock

from logprep.generator.http.sender import Sender  # Adjust import as needed


class TestSender:
    def setup_method(self):
        self.mock_batcher = mock.MagicMock()
        self.mock_output = mock.MagicMock()

        self.sender = Sender(self.mock_batcher, self.mock_output)

    def test_init(self):
        assert self.sender.batcher is self.mock_batcher
        assert self.sender.output is self.mock_output

    def test_send_batch_calls_batcher_and_output(self):
        """Ensure send_batch calls batcher.process_batches and output.store."""
        mock_batch = ["msg1", "msg2", "msg3"]
        self.mock_batcher.process_batches.return_value = mock_batch

        self.sender.send_batch()

        self.mock_batcher.process_batches.assert_called_once()
        self.mock_output.store.assert_called_once_with(mock_batch)
