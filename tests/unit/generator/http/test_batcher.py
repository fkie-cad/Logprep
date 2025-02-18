# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
import random
from unittest import mock

from logprep.generator.http.batcher import Batcher
from logprep.util.defaults import DEFAULT_BATCH_SIZE, DEFAULT_BATCH_TIME


class TestBatcher:

    def setup_method(self):
        self.mock_file_loader = mock.MagicMock()
        self.mock_output = mock.MagicMock()
        self.mock_file_loader.read_lines.return_value = iter(
            ["msg1", "msg2", "msg3", "msg4", "msg5", "msg6"]
        )
        self.mock_file_loader.__enter__.return_value = self.mock_file_loader
        self.mock_file_loader.__exit__.return_value = None

    def test_init(self):
        batcher = Batcher(self.mock_file_loader, self.mock_output)
        assert batcher
        assert batcher.file_loader is self.mock_file_loader
        assert batcher.output is self.mock_output

    def test_init_defaults(self):
        batcher = Batcher(self.mock_file_loader, self.mock_output)
        assert batcher.batch_size is DEFAULT_BATCH_SIZE
        assert batcher.batch_time is DEFAULT_BATCH_TIME

    def test_init_overwrites_defaults(self):
        random_size = random.randint(1, 100000)
        random_time = random.random()
        batcher = Batcher(self.mock_file_loader, self.mock_output, random_size, random_time)
        assert batcher.batch_size is random_size
        assert batcher.batch_time is random_time

    def test_batcher_sends_everything_at_once(self):
        batcher = Batcher(
            self.mock_file_loader, output=self.mock_output, batch_size=10, batch_time=10
        )
        with (mock.patch.object(batcher, "_send_batch") as mock_send_batch,):
            batcher.process_batches()

            mock_send_batch.assert_any_call(["msg1", "msg2", "msg3", "msg4", "msg5", "msg6"])
            assert mock_send_batch.call_count == 1

    def test_batcher_sends_batches_by_size(self):
        batcher = Batcher(
            self.mock_file_loader, output=self.mock_output, batch_size=3, batch_time=10
        )

        with (mock.patch.object(batcher, "_send_batch") as mock_send_batch,):
            batcher.process_batches()

            mock_send_batch.assert_any_call(["msg1", "msg2", "msg3"])
            mock_send_batch.assert_any_call(["msg4", "msg5", "msg6"])
            assert mock_send_batch.call_count == 2

    def test_batcher_sends_batches_by_time(self):

        batcher = Batcher(
            self.mock_file_loader, output=self.mock_output, batch_size=10, batch_time=0.3
        )

        with (
            mock.patch("time.time", side_effect=[0, 0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65]),
            mock.patch.object(batcher, "_send_batch") as mock_send_batch,
        ):
            batcher.process_batches()

            mock_send_batch.assert_any_call(["msg1", "msg2", "msg3", "msg4"])
            mock_send_batch.assert_any_call(["msg5", "msg6"])
            assert mock_send_batch.call_count == 2

    def test_send_batch(self, caplog):
        caplog.set_level(logging.INFO)
        batcher = Batcher(
            self.mock_file_loader, output=self.mock_output, batch_size=10, batch_time=10
        )
        batcher._send_batch(["msg1", "msg2"])

        assert "Sending batch of 2 messages." in caplog.text
        assert batcher.output.call_count == 1
