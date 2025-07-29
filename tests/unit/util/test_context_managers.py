# pylint: disable=missing-function-docstring
import logging
from unittest import mock

from logprep.util.context_managers import logqueue_listener

LOGGER = logging.getLogger()


class TestContextManagers:
    @mock.patch("logprep.util.context_managers.LogprepMPQueueListener")
    def test_logqueue_listener_is_being_used_for_logger(self, mock_listener_cls):
        mock_listener = mock.Mock()
        mock_listener_cls.return_value = mock_listener

        with logqueue_listener(LOGGER.name):
            pass

        assert mock_listener.start.called, "Listener start() was not called"
        assert mock_listener.stop.called, "Listener stop() was not called"

    @mock.patch("logprep.util.context_managers.LogprepMPQueueListener")
    def test_logqueue_listener_is_not_being_used_for_logger(self, mock_listener_cls):
        mock_listener = mock.Mock()
        mock_listener_cls.return_value = mock_listener

        with logqueue_listener("not the logger name"):
            pass

        assert not mock_listener.start.called, "Listener start() was called"
        assert not mock_listener.stop.called, "Listener stop() was called"
