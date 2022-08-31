"""module for processor registry
    it is used to check if a processor is known to the system.
    you have to register new processors here by import them and add to `ConnectorRegistry.mapping`
"""
from logprep.connector.confluent_kafka.input import ConfluentKafkaInput
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.connector.json.input import JsonInput


class ConnectorRegistry:
    """Connector Registry"""

    mapping = {
        "confluent_kafka_input": ConfluentKafkaInput,
        "confluent_kafka_output": ConfluentKafkaOutput,
        "json_input": JsonInput,
    }

    @classmethod
    def get_connector_class(cls, processor_type):
        """return the processor class for a given type

        Parameters
        ----------
        processor_type : str
            the processor type

        Returns
        -------
        _type_
            _description_
        """
        return cls.mapping.get(processor_type)
