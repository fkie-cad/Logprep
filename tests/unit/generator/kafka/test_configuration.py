# pylint: disable=too-few-public-methods
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
from pathlib import Path, PosixPath

from logprep.generator.kafka.configuration import (
    Configuration,
    Consumer,
    Kafka,
    Producer,
    load_config,
)

EXPECTED_CONFIG = Configuration(
    # profile=False,
    source_file=PosixPath("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
    count=400000,
    source_count=5,
    logging_level="DEBUG",
    process_count=2,
    kafka=Kafka(
        bootstrap_servers=["localhost:9092"],
        consumer=Consumer(topic="consumer", group_id="load-tester", timeout=1.0),
        producer=Producer(
            acks=0,
            compression_type="none",
            queue_buffering_max_messages=10000,
            linger_ms=5000,
            flush_timeout=30.0,
            topic="load-tester",
        ),
        ssl=None,
    ),
)


class TestConfiguration:
    def test_load_configuration_with_source_file(self):
        config = load_config(
            Path("tests/testdata/generator/kafka/config.yml"),
            Path("tests/testdata/generator/kafka/wineventlog_raw.jsonl"),
        )
        assert config == EXPECTED_CONFIG

    def test_load_configuration_without_source_file(self):
        expected = EXPECTED_CONFIG.model_copy()
        expected.source_file = None
        config = load_config(Path("tests/testdata/generator/kafka/config.yml"))
        assert config == expected
