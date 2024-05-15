import logging
import logging.config
from socket import gethostname

import pytest

from logprep.util.defaults import DEFAULT_LOG_CONFIG
from logprep.util.logging import LogprepFormatter


class TestLogprepFormatter:

    def test_default_log_config(self):
        logging.config.dictConfig(DEFAULT_LOG_CONFIG)
        logger = logging.getLogger("test")
        assert isinstance(logger.root.handlers[1].formatter, LogprepFormatter)

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
