"""
KafkaConfluentGeneratorOutput
==========

The logprep confluent kafka generator inheriting from the confluent kafka connector output.
Sends the documents writen by the generator to a topic endpoint.
"""

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput


class ConfluentKafkaGeneratorOutput(ConfluentKafkaOutput):
    """Output class inheriting from the connector output class"""

    def store(self, document: dict | str) -> None:
        if isinstance(document, str):
            topic, _, payload = document.partition(",")
            self.store_custom(payload, topic)
        else:
            super().store(document)

        # try:
        #     self.metrics.number_of_processed_events += document.count(";") + 1
        #     documents = [json.loads(item) for item in document.split(";")]
        #     for item in documents:
        #         self._producer.produce(target, value=self._encoder.encode(item))
        #     logger.debug("Produced message %s to topic %s", str(document), target)
        #     self._producer.poll(self._config.send_timeout)
        #     self.metrics.processed_batches += 1
