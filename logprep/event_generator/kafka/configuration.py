""" Contains configuration class with configuration validation """

# pylint: disable=too-few-public-methods
import sys
from pathlib import Path
from typing import List, Union

import yaml
from pydantic import BaseModel, ValidationError


def load_config(config_path: Path, documents_file: Path = None):
    """Load and validate configuration"""
    with config_path.open("r", encoding="utf-8") as config_file:
        config_dict = yaml.safe_load(config_file)
    config = validate(config_dict)
    config.source_file = documents_file
    config.process_count = max(min(config.process_count, config.count), 1)
    return config


class Key(BaseModel):
    """Configuration for SSL key"""

    location: Path
    password: str | None = None


class SSL(BaseModel):
    """Configuration for SSL authentication"""

    ca_location: Path
    certificate_location: Path
    key: Key


class Consumer(BaseModel):
    """Configuration for Kafka consumer"""

    topic: str
    group_id: str
    timeout: float | None = 1.0


class Producer(BaseModel):
    """Configuration for Kafka producer"""

    acks: Union[int, str] | None = 0
    compression_type: str | None = "none"
    queue_buffering_max_messages: int | None = 10**4
    linger_ms: int | None = 5000
    flush_timeout: float | None = 30.0
    topic: str


class Kafka(BaseModel):
    """Configuration for Kafka"""

    bootstrap_servers: List[str]
    consumer: Consumer
    producer: Producer
    ssl: SSL | None = None


class Configuration(BaseModel):
    """Configuration for load-tester"""

    profile: bool | None = False
    source_file: Path | None = None
    count: int
    source_count: int
    logging_level: str | None = "INFO"
    process_count: int | None = 1
    target_send_per_sec: int | None = 0
    kafka: Kafka


def validate(config):
    """Validate configuration and return Configuration object"""
    try:
        return Configuration(**config)
    except ValidationError as error:
        print("Can't validate config:")
        for item in error.errors():
            print(f'{item["msg"]}: "{".".join(item["loc"])}"')
        sys.exit(1)
