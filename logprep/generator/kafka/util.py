"""Contains utility functions"""

from logging import Logger
from pathlib import Path

import numpy as np

from logprep.generator.kafka.configuration import Configuration


def get_avg_size_mb(source_file: Path) -> float:
    """Get average document size in source file"""
    with source_file.open("r", encoding="utf-8") as input_docs:
        docs = input_docs.readlines()
        size = sum(len(doc.encode("utf-8")) for doc in docs) / len(docs)
        return round(size) / (10**6)


def print_startup_info(config: Configuration, logger: Logger):
    """Print startup information for the load-tester"""
    logger.info(f"Inserting: {config.count} records using {config.process_count} processes")
    if config.source_file:
        per_record_size = get_avg_size_mb(config.source_file)
        logger.debug(f"Estimated per record size: {per_record_size:.2E} MB")
        logger.info(f"Estimated total size: {per_record_size * config.process_count:.2E} MB")


def print_results(config: Configuration, logger: Logger, shared_dict: dict):
    """Print results for complete run of the load-tester"""
    sent_cnt = int(
        np.sum(
            [
                value
                for key, value in shared_dict.items()
                if key.endswith("_sent") and value is not None
            ]
        )
    )
    logger.info(f"Inserted {sent_cnt} records")
    if sent_cnt == 0:
        return

    times = [value for key, value in shared_dict.items() if key.endswith("_time")]
    max_time = np.max(times) * 1000
    logger.info(f"Insertion finished and took {max_time} ms")
    avg_time = np.average(times) / config.count * 1000
    logger.debug(f"Average insertion time per record: {avg_time} ms")
