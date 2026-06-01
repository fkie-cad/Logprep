"""module for processor registry
it is used to check if a processor is known to the system.
you have to register new processors here by import them and add to `ProcessorRegistry.mapping`
"""

from importlib import import_module
from typing import Callable

from logprep.abc.connector import Connector
from logprep.abc.processor import Processor

<<<<<<< HEAD
=======
from logprep.ng.abc.connector import Connector as NgConnector

>>>>>>> 25dbe2b1 (fix mypy issues)
from logprep.ng.abc.processor import Processor as NgProcessor
from logprep.processor.base.rule import Rule


def _import_class(
    class_name: str,
    module_name: str,
) -> type:
    """Import class from module by name."""
    module = import_module(module_name)
    return getattr(module, class_name)


class Registry:
    """Lazy component registry that imports components only when requested."""

    mapping: dict[str, Callable[[], type[Processor | Connector | NgProcessor | NgConnector]]] = {
        # Processors
        "amides": lambda: _import_class("Amides", "logprep.processor.amides.processor"),
        "calculator": lambda: _import_class("Calculator", "logprep.processor.calculator.processor"),
        "clusterer": lambda: _import_class("Clusterer", "logprep.processor.clusterer.processor"),
        "concatenator": lambda: _import_class(
            "Concatenator", "logprep.processor.concatenator.processor"
        ),
        "datetime_extractor": lambda: _import_class(
            "DatetimeExtractor", "logprep.processor.datetime_extractor.processor"
        ),
        "decoder": lambda: _import_class("Decoder", "logprep.processor.decoder.processor"),
        "deleter": lambda: _import_class("Deleter", "logprep.processor.deleter.processor"),
        "dissector": lambda: _import_class("Dissector", "logprep.processor.dissector.processor"),
        "deduplicator": lambda: _import_class(
            "Deduplicator", "logprep.processor.deduplicator.processor"
        ),
        "domain_label_extractor": lambda: _import_class(
            "DomainLabelExtractor", "logprep.processor.domain_label_extractor.processor"
        ),
        "domain_resolver": lambda: _import_class(
            "DomainResolver", "logprep.processor.domain_resolver.processor"
        ),
        "dropper": lambda: _import_class("Dropper", "logprep.processor.dropper.processor"),
        "field_manager": lambda: _import_class(
            "FieldManager", "logprep.processor.field_manager.processor"
        ),
        "generic_adder": lambda: _import_class(
            "GenericAdder", "logprep.processor.generic_adder.processor"
        ),
        "generic_resolver": lambda: _import_class(
            "GenericResolver", "logprep.processor.generic_resolver.processor"
        ),
        "geoip_enricher": lambda: _import_class(
            "GeoipEnricher", "logprep.processor.geoip_enricher.processor"
        ),
        "grokker": lambda: _import_class("Grokker", "logprep.processor.grokker.processor"),
        "ip_informer": lambda: _import_class(
            "IpInformer", "logprep.processor.ip_informer.processor"
        ),
        "key_checker": lambda: _import_class(
            "KeyChecker", "logprep.processor.key_checker.processor"
        ),
        "labeler": lambda: _import_class("Labeler", "logprep.processor.labeler.processor"),
        "list_comparison": lambda: _import_class(
            "ListComparison", "logprep.processor.list_comparison.processor"
        ),
        "network_comparison": lambda: _import_class(
            "NetworkComparison", "logprep.processor.network_comparison.processor"
        ),
        "ng_amides": lambda: _import_class("Amides", "logprep.ng.processor.amides.processor"),
        "ng_calculator": lambda: _import_class(
            "Calculator", "logprep.ng.processor.calculator.processor"
        ),
        "ng_clusterer": lambda: _import_class(
            "Clusterer", "logprep.ng.processor.clusterer.processor"
        ),
        "ng_concatenator": lambda: _import_class(
            "Concatenator", "logprep.ng.processor.concatenator.processor"
        ),
        "ng_deleter": lambda: _import_class("Deleter", "logprep.ng.processor.deleter.processor"),
        "ng_decoder": lambda: _import_class("Decoder", "logprep.ng.processor.decoder.processor"),
        "ng_datetime_extractor": lambda: _import_class(
            "DatetimeExtractor", "logprep.ng.processor.datetime_extractor.processor"
        ),
        "ng_dissector": lambda: _import_class(
            "Dissector", "logprep.ng.processor.dissector.processor"
        ),
        "ng_deduplicator": lambda: _import_class(
            "Deduplicator", "logprep.ng.processor.deduplicator.processor"
        ),
        "ng_domain_label_extractor": lambda: _import_class(
            "DomainLabelExtractor",
            "logprep.ng.processor.domain_label_extractor.processor",
        ),
        "ng_domain_resolver": lambda: _import_class(
            "DomainResolver", "logprep.ng.processor.domain_resolver.processor"
        ),
        "ng_dropper": lambda: _import_class("Dropper", "logprep.ng.processor.dropper.processor"),
        "ng_field_manager": lambda: _import_class(
            "FieldManager", "logprep.ng.processor.field_manager.processor"
        ),
        "ng_generic_adder": lambda: _import_class(
            "GenericAdder", "logprep.ng.processor.generic_adder.processor"
        ),
        "ng_generic_resolver": lambda: _import_class(
            "GenericResolver", "logprep.ng.processor.generic_resolver.processor"
        ),
        "ng_geoip_enricher": lambda: _import_class(
            "GeoipEnricher", "logprep.ng.processor.geoip_enricher.processor"
        ),
        "ng_grokker": lambda: _import_class("Grokker", "logprep.ng.processor.grokker.processor"),
        "ng_ip_informer": lambda: _import_class(
            "IpInformer", "logprep.ng.processor.ip_informer.processor"
        ),
        "ng_key_checker": lambda: _import_class(
            "KeyChecker", "logprep.ng.processor.key_checker.processor"
        ),
        "ng_labeler": lambda: _import_class("Labeler", "logprep.ng.processor.labeler.processor"),
        "ng_list_comparison": lambda: _import_class(
            "ListComparison", "logprep.ng.processor.list_comparison.processor"
        ),
        "ng_network_comparison": lambda: _import_class(
            "NetworkComparison", "logprep.ng.processor.network_comparison.processor"
        ),
        "ng_replacer": lambda: _import_class("Replacer", "logprep.ng.processor.replacer.processor"),
        "ng_requester": lambda: _import_class(
            "Requester", "logprep.ng.processor.requester.processor"
        ),
        "ng_string_splitter": lambda: _import_class(
            "StringSplitter", "logprep.ng.processor.string_splitter.processor"
        ),
        "ng_template_replacer": lambda: _import_class(
            "TemplateReplacer", "logprep.ng.processor.template_replacer.processor"
        ),
        "ng_timestamp_differ": lambda: _import_class(
            "TimestampDiffer", "logprep.ng.processor.timestamp_differ.processor"
        ),
        "ng_timestamper": lambda: _import_class(
            "Timestamper", "logprep.ng.processor.timestamper.processor"
        ),
        "ng_pre_detector": lambda: _import_class(
            "PreDetector", "logprep.ng.processor.pre_detector.processor"
        ),
        "ng_pseudonymizer": lambda: _import_class(
            "Pseudonymizer", "logprep.ng.processor.pseudonymizer.processor"
        ),
        "ng_selective_extractor": lambda: _import_class(
            "SelectiveExtractor", "logprep.ng.processor.selective_extractor.processor"
        ),
        "pre_detector": lambda: _import_class(
            "PreDetector", "logprep.processor.pre_detector.processor"
        ),
        "pseudonymizer": lambda: _import_class(
            "Pseudonymizer", "logprep.processor.pseudonymizer.processor"
        ),
        "requester": lambda: _import_class("Requester", "logprep.processor.requester.processor"),
        "replacer": lambda: _import_class("Replacer", "logprep.processor.replacer.processor"),
        "selective_extractor": lambda: _import_class(
            "SelectiveExtractor", "logprep.processor.selective_extractor.processor"
        ),
        "string_splitter": lambda: _import_class(
            "StringSplitter", "logprep.processor.string_splitter.processor"
        ),
        "template_replacer": lambda: _import_class(
            "TemplateReplacer", "logprep.processor.template_replacer.processor"
        ),
        "timestamp_differ": lambda: _import_class(
            "TimestampDiffer", "logprep.processor.timestamp_differ.processor"
        ),
        "timestamper": lambda: _import_class(
            "Timestamper", "logprep.processor.timestamper.processor"
        ),
        # Connectors
        "json_input": lambda: _import_class("JsonInput", "logprep.connector.json.input"),
        "jsonl_input": lambda: _import_class("JsonlInput", "logprep.connector.jsonl.input"),
        "file_input": lambda: _import_class("FileInput", "logprep.connector.file.input"),
        "dummy_input": lambda: _import_class("DummyInput", "logprep.connector.dummy.input"),
        "dummy_output": lambda: _import_class("DummyOutput", "logprep.connector.dummy.output"),
        "confluentkafka_input": lambda: _import_class(
            "ConfluentKafkaInput", "logprep.connector.confluent_kafka.input"
        ),
        "confluentkafka_output": lambda: _import_class(
            "ConfluentKafkaOutput", "logprep.connector.confluent_kafka.output"
        ),
        "console_output": lambda: _import_class(
            "ConsoleOutput", "logprep.connector.console.output"
        ),
        "jsonl_output": lambda: _import_class("JsonlOutput", "logprep.connector.jsonl.output"),
        "opensearch_output": lambda: _import_class(
            "OpensearchOutput", "logprep.connector.opensearch.output"
        ),
        "http_input": lambda: _import_class("HttpInput", "logprep.connector.http.input"),
        "http_output": lambda: _import_class("HttpOutput", "logprep.connector.http.output"),
        "http_generator_output": lambda: _import_class(
            "HttpGeneratorOutput", "logprep.generator.http.output"
        ),
        "confluentkafka_generator_output": lambda: _import_class(
            "ConfluentKafkaGeneratorOutput", "logprep.generator.confluent_kafka.output"
        ),
        "s3_output": lambda: _import_class("S3Output", "logprep.connector.s3.output"),
        "ng_http_input": lambda: _import_class("HttpInput", "logprep.ng.connector.http.input"),
        "ng_confluentkafka_input": lambda: _import_class(
            "ConfluentKafkaInput", "logprep.ng.connector.confluent_kafka.input"
        ),
        "ng_dummy_input": lambda: _import_class("DummyInput", "logprep.ng.connector.dummy.input"),
        "ng_json_input": lambda: _import_class("JsonInput", "logprep.ng.connector.json.input"),
        "ng_file_input": lambda: _import_class("FileInput", "logprep.ng.connector.file.input"),
        "ng_dummy_output": lambda: _import_class(
            "DummyOutput", "logprep.ng.connector.dummy.output"
        ),
        "ng_console_output": lambda: _import_class(
            "ConsoleOutput", "logprep.ng.connector.console.output"
        ),
        "ng_jsonl_output": lambda: _import_class(
            "JsonlOutput", "logprep.ng.connector.jsonl.output"
        ),
        "ng_opensearch_output": lambda: _import_class(
            "OpensearchOutput", "logprep.ng.connector.opensearch.output"
        ),
        "ng_confluentkafka_output": lambda: _import_class(
            "ConfluentKafkaOutput", "logprep.ng.connector.confluent_kafka.output"
        ),
    }

    _resolved_classes: dict[str, type[Processor | Connector | NgProcessor]] = {}

    @classmethod
    def get_class(cls, component_type: str) -> type[Processor | Connector | NgProcessor | NgConnector]:
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
        processor_class = cls._resolved_classes.get(component_type)
        if processor_class is not None:
            return processor_class

        processor_class_factory = cls.mapping.get(component_type)
        if processor_class_factory is None:
            raise ValueError(f"Unknown processor type: {component_type}")

        processor_class = processor_class_factory()
        cls._resolved_classes[component_type] = processor_class
        return processor_class

    @classmethod
    def get_rule_class_by_rule_definition(cls, rule_definition: dict) -> type[Rule]:
        """return the rule class for a given rule type

        Parameters
        ----------
        rule_definition : str
            the processor type

        Returns
        -------
        rule_class
            The class of the rule

        Raises
        ------
        ValueError
            if the rule type is unknown
        """
        processor_type = {elem for elem in rule_definition if elem in cls.mapping}
        if not processor_type:
            raise ValueError("Unknown rule type")
        processor_type = processor_type.pop()
        if not isinstance(processor_type, str):
            raise ValueError("Unknown rule type")
        processor_class = cls.get_class(processor_type)
        if not issubclass(processor_class, (Processor, NgProcessor)):
            # TODO remove after ng integration
            raise ValueError(f"Unknown processor type: {processor_type}")
        rule_class = processor_class.rule_class
        if rule_class is None:
            raise ValueError(f"Rule type not set in processor: {processor_type}")
        return rule_class
