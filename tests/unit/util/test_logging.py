# pylint: disable=missing-docstring
import logging
import logging.config
import logging.handlers
import multiprocessing as mp
import queue
from socket import gethostname

import pytest
from _pytest.logging import LogCaptureHandler

from logprep.util.defaults import DEFAULT_LOG_CONFIG
from logprep.util.logging import LogprepFormatter


def setup_module():
    logging.config.dictConfig(DEFAULT_LOG_CONFIG)


class TestLogDictConfig:
    """this tests the logprep.util.defaults.DEFAULT_LOG_CONFIG dict"""

    def test_console_logger_uses_logprep_formatter(self):
        logger = logging.getLogger("console")
        assert isinstance(logger.handlers[0].formatter, LogprepFormatter)

    def test_root_logger_has_only_quehandler(self):
        logger = logging.getLogger("root")
        assert len(logger.handlers) == 3, "queuehandler and 2 logcapture handlers from pytest"
        assert isinstance(logger.handlers[0], logging.handlers.QueueHandler)
        # these handlers are pytest handlers and won't be available in production
        assert isinstance(logger.handlers[1], LogCaptureHandler)
        assert isinstance(logger.handlers[2], LogCaptureHandler)

    def test_queuhandler_uses_multiprocessing_queue(self):
        logger = logging.getLogger("root")
        assert isinstance(logger.handlers[0].queue, mp.queues.Queue)
        assert not isinstance(logger.handlers[0].queue, queue.Queue)

    @pytest.mark.parametrize(
        ("logger_name", "expected_level"),
        [
            ("filelock", "ERROR"),
            ("urllib3.connectionpool", "ERROR"),
            ("opensearch", "ERROR"),
        ],
    )
    def test_default_log_levels(self, logger_name, expected_level):
        loglevel = logging.getLogger(logger_name).level
        loglevel = logging.getLevelName(loglevel)
        assert loglevel == expected_level


class TestLogprepFormatter:

    def test_formatter_init_with_default(self):
        default_formatter_config = DEFAULT_LOG_CONFIG["formatters"]["logprep"]
        formatter = LogprepFormatter(
            fmt=default_formatter_config["format"], datefmt=default_formatter_config["datefmt"]
        )
        assert isinstance(formatter, LogprepFormatter)

    def test_format_returns_str(self):
        default_formatter_config = DEFAULT_LOG_CONFIG["formatters"]["logprep"]
        formatter = LogprepFormatter(
            fmt=default_formatter_config["format"], datefmt=default_formatter_config["datefmt"]
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=None,
            exc_info=None,
        )
        formatted_record = formatter.format(record)
        assert isinstance(formatted_record, str)
        assert "test message" in formatted_record
        assert "INFO" in formatted_record

    @pytest.mark.parametrize(
        "custom_format, expected",
        [
            ("%(asctime)-15s %(hostname)-5s %(name)-5s %(levelname)-8s: %(message)s", gethostname),
        ],
    )
    def test_format_custom_format(self, custom_format, expected):
        default_formatter_config = DEFAULT_LOG_CONFIG["formatters"]["logprep"]
        formatter = LogprepFormatter(fmt=custom_format, datefmt=default_formatter_config["datefmt"])
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=None,
            exc_info=None,
        )
        formatted_record = formatter.format(record)
        assert isinstance(formatted_record, str)
        assert "test message" in formatted_record
        assert "INFO" in formatted_record
        assert expected() in formatted_record
