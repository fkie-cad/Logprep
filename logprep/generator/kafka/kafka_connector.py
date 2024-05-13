"""For retrieval and insertion of data from and into Kafka."""

import json
from typing import Optional

from confluent_kafka import Consumer, Producer

from logprep.generator.kafka.configuration import Kafka


class KafkaProducer:
    """Inserts data into Kafka."""

    def __init__(self, config: Kafka):
        self._producer_topic = config.producer.topic
        self._flush_timeout = config.producer.flush_timeout

        self._config = {
            "bootstrap.servers": ",".join(config.bootstrap_servers),
            "acks": config.producer.acks,
            "compression.type": config.producer.compression_type,
            "queue.buffering.max.messages": config.producer.queue_buffering_max_messages,
            "linger.ms": config.producer.linger_ms,
        }

        if config.ssl:
            ssl_config = {
                "security.protocol": "SSL",
                "ssl.ca.location": config.ssl.ca_location,
                "ssl.certificate.location": config.ssl.certificate_location,
                "ssl.key.location": config.ssl.key.location,
                "ssl.key.password": config.ssl.key.password,
            }
            self._config.update(ssl_config)

        self._producer = Producer(self._config)

    def store(self, document: str):
        """Write document into Kafka"""
        try:
            self._producer.produce(self._producer_topic, value=document)
            self._producer.poll(0)
        except BufferError:
            self._producer.flush(timeout=self._flush_timeout)

    def shut_down(self):
        """Gracefully close Kafka producer"""
        if self._producer is not None:
            self._producer.flush(self._flush_timeout)


class KafkaConsumer:
    """Get data from Kafka."""

    def __init__(self, config: Kafka):
        self._consumer_topic = config.producer.topic

        self._config = {
            "bootstrap.servers": ",".join(config.bootstrap_servers),
            "group.id": config.consumer.group_id,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }

        if config.ssl:
            ssl_config = {
                "security.protocol": "SSL",
                "ssl.ca.location": config.ssl.ca_location,
                "ssl.certificate.location": config.ssl.certificate_location,
                "ssl.key.location": config.ssl.key.location,
                "ssl.key.password": config.ssl.key.password,
            }
            self._config.update(ssl_config)

        self._consumer = Consumer(self._config)
        self._consumer.subscribe([config.consumer.topic])

    def get(self, timeout: float) -> Optional[str]:
        """Get document from Kafka"""
        record = self._consumer.poll(timeout=timeout)
        if not record:
            return None

        if record.error():
            raise record.error()
        return json.loads(record.value().decode("utf-8"))

    def shut_down(self):
        """Gracefully close Kafka consumer"""
        if self._consumer is not None:
            self._consumer.close()
