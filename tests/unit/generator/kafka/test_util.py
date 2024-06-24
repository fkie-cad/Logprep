# pylint: disable=too-few-public-methods
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
from pathlib import Path
from unittest.mock import MagicMock

from logprep.generator.kafka.configuration import load_config
from logprep.generator.kafka.util import (
    get_avg_size_mb,
    print_results,
    print_startup_info,
)


class TestUtil:
    def test_get_avg_size_mb(self):
        assert (
            get_avg_size_mb(Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"))
            == 0.001621
        )

    def test_print_results_with_empty_shared_dict(self):
        config = load_config(
            Path("tests/testdata/generator/kafka/config.yml"),
            Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
        )
        logger = MagicMock()
        print_results(config, logger, {})
        logger.info.assert_called_with("Inserted 0 records")

    def test_print_results_with_filled_shared_dict(self):
        config = load_config(
            Path("tests/testdata/generator/kafka/config.yml"),
            Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
        )
        logger = MagicMock()
        print_results(config, logger, {"foo_sent": 2, "bar_sent": 3, "foo_time": 4, "bar_time": 8})
        logger.info.assert_called_with("Insertion finished and took 8000 ms")

    def test_print_startup_info_with_source_file(self):
        config = load_config(
            Path("tests/testdata/generator/kafka/config.yml"),
            Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
        )
        logger = MagicMock()
        print_startup_info(config, logger)
        logger.info.assert_called_with("Estimated total size: 3.24E-03 MB")

    def test_print_startup_info_without_source_file(self):
        config = load_config(
            Path("tests/testdata/generator/kafka/config.yml"),
            Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
        )
        config.source_file = None
        logger = MagicMock()
        print_startup_info(config, logger)
        logger.info.assert_called_with("Inserting: 400000 records using 2 processes")
