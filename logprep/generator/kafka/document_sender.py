"""For repeatedly sending documents to Kafka"""

import itertools
from logging import Logger
from time import perf_counter
from uuid import uuid4

from logprep.generator.kafka.configuration import Configuration
from logprep.generator.kafka.kafka_connector import KafkaProducer


class DocumentSender:
    """Sends documents to Kafka until desired count has been reached"""

    def __init__(self, config: Configuration, logger: Logger):
        self._kafka_producer = KafkaProducer(config.kafka)
        self._target_time_per_sec = (
            1.0 / config.target_send_per_sec if config.target_send_per_sec else 0
        )
        self._logger = logger

    def send(self, cnt: int, docs: list):
        """Send documents to Kafka until desired count has been reached"""
        if cnt <= 0:
            return 0

        wait_time = self._target_time_per_sec

        last_idx = -1
        weighted_sending_time = None
        sent = 0
        start_interval_sec = perf_counter()
        for idx, doc in enumerate(itertools.cycle(docs)):
            start = perf_counter()
            self._kafka_producer.store(f'{doc}{uuid4()}"}}')
            sent += 1
            if sent >= cnt:
                self._logger.debug("Documents sent per seconds: %s", idx - last_idx)
                return sent
            now = perf_counter()
            sending_time = now - start
            weighted_sending_time = (
                (weighted_sending_time + sending_time) / 2.0
                if weighted_sending_time
                else sending_time
            )

            passed_time = now - start_interval_sec
            if passed_time >= 1:
                start_interval_sec = now
                self._logger.debug(
                    "Documents sent per seconds: %s", round((idx - last_idx) / passed_time)
                )
                last_idx = idx
                wait_time = self._target_time_per_sec - weighted_sending_time

            if wait_time <= 0:
                wait_time = self._target_time_per_sec
            now = perf_counter()
            wait_end = now + wait_time
            while now < wait_end:
                now = perf_counter()
        return 0

    def shut_down(self):
        """Gracefully close Kafka producer"""
        self._kafka_producer.shut_down()
