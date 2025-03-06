"""
KafkaConfluentGeneratorOutput
==========

The logprep confluent kafka generator inheriting from the confluent kafka connector output.
Sends the documents writen by the generator to a topic endpoint.
"""

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput


class ConfluentKafkaGeneratorOutput(ConfluentKafkaOutput):
    """Output class inheriting from the connector output class"""

    def store(self, document: str) -> None:
        """Store a document in the producer topic.

        Parameters
        ----------
        document : str
        Document to store.
        """
        topic, _, payload = document.partition(",")
        self.store_custom(payload, topic)
