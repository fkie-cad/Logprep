"""module for processor registry
    it is used to check if a processor is known to the system.
    you have to register new processors here by import them and add to `ConnectorRegistry.mapping`
"""
from logprep.connector.confluent_kafka.input import ConfluentKafkaInput
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.connector.dummy.input import DummyInput
from logprep.connector.json.input import JsonInput
from logprep.connector.jsonl.input import JsonlInput


class ConnectorRegistry:
    """Connector Registry"""

    mapping = {
        "json_input": JsonInput,
        "jsonl_input": JsonlInput,
        "dummy_input": DummyInput,
        "confluentkafka_input": ConfluentKafkaInput,
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
