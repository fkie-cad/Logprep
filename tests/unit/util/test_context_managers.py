# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
import logging
from copy import deepcopy
from unittest import mock

from logprep.util.context_managers import logqueue_listener, disable_loggers

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

    def test_disabled_loggers_disables_enabled_loggers(self):
        original_loggers = deepcopy(logging.root.manager.loggerDict)
        try:
            enabled_logger = logging.getLogger("test_logger_enabled")
            enabled_logger.disabled = False

            disabled_logger = logging.getLogger("test_logger_disabled")
            disabled_logger.disabled = True

            logging.root.manager.loggerDict["not_a_logger"] = "not_a_logger"

            with disable_loggers():
                assert enabled_logger.disabled is True
                assert disabled_logger.disabled is True
        finally:
            logging.root.manager.loggerDict = original_loggers
        assert enabled_logger.disabled is False
        assert disabled_logger.disabled is True
