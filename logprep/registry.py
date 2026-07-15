"""module for processor registry
it is used to check if a processor is known to the system.
you have to register new processors here by import them and add to `Registry`
"""

from importlib import import_module
from typing import TypeAlias

from logprep.abc.connector import Connector
from logprep.abc.processor import Processor
from logprep.ng.abc.connector import Connector as NgConnector
from logprep.ng.abc.processor import Processor as NgProcessor
from logprep.processor.base.rule import Rule

ComponentTypeMap: TypeAlias = dict[str, str]


def _import_class(dotted_path: str) -> type:
    """Import a class from a dotted path string (e.g. 'my.module.ClassName')."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    return getattr(import_module(module_path), class_name)


class Registry:
    """Lazy component registry that imports components only when requested."""

    # pylint: disable=line-too-long
    _non_ng_mapping: ComponentTypeMap = {
        # Processors
        "amides": "logprep.processor.amides.processor.Amides",
        "calculator": "logprep.processor.calculator.processor.Calculator",
        "clusterer": "logprep.processor.clusterer.processor.Clusterer",
        "concatenator": "logprep.processor.concatenator.processor.Concatenator",
        "datetime_extractor": "logprep.processor.datetime_extractor.processor.DatetimeExtractor",
        "decoder": "logprep.processor.decoder.processor.Decoder",
        "deduplicator": "logprep.processor.deduplicator.processor.Deduplicator",
        "deleter": "logprep.processor.deleter.processor.Deleter",
        "dissector": "logprep.processor.dissector.processor.Dissector",
        "domain_label_extractor": "logprep.processor.domain_label_extractor.processor.DomainLabelExtractor",
        "domain_resolver": "logprep.processor.domain_resolver.processor.DomainResolver",
        "dropper": "logprep.processor.dropper.processor.Dropper",
        "field_manager": "logprep.processor.field_manager.processor.FieldManager",
        "generic_adder": "logprep.processor.generic_adder.processor.GenericAdder",
        "generic_resolver": "logprep.processor.generic_resolver.processor.GenericResolver",
        "geoip_enricher": "logprep.processor.geoip_enricher.processor.GeoipEnricher",
        "grokker": "logprep.processor.grokker.processor.Grokker",
        "ip_informer": "logprep.processor.ip_informer.processor.IpInformer",
        "key_checker": "logprep.processor.key_checker.processor.KeyChecker",
        "labeler": "logprep.processor.labeler.processor.Labeler",
        "list_comparison": "logprep.processor.list_comparison.processor.ListComparison",
        "network_comparison": "logprep.processor.network_comparison.processor.NetworkComparison",
        "pre_detector": "logprep.processor.pre_detector.processor.PreDetector",
        "pseudonymizer": "logprep.processor.pseudonymizer.processor.Pseudonymizer",
        "replacer": "logprep.processor.replacer.processor.Replacer",
        "requester": "logprep.processor.requester.processor.Requester",
        "selective_extractor": "logprep.processor.selective_extractor.processor.SelectiveExtractor",
        "string_splitter": "logprep.processor.string_splitter.processor.StringSplitter",
        "template_replacer": "logprep.processor.template_replacer.processor.TemplateReplacer",
        "timestamp_differ": "logprep.processor.timestamp_differ.processor.TimestampDiffer",
        "timestamper": "logprep.processor.timestamper.processor.Timestamper",
        # Connectors
        "confluentkafka_input": "logprep.connector.confluent_kafka.input.ConfluentKafkaInput",
        "confluentkafka_output": "logprep.connector.confluent_kafka.output.ConfluentKafkaOutput",
        "confluentkafka_generator_output": "logprep.generator.confluent_kafka.output.ConfluentKafkaGeneratorOutput",
        "console_output": "logprep.connector.console.output.ConsoleOutput",
        "dummy_input": "logprep.connector.dummy.input.DummyInput",
        "dummy_output": "logprep.connector.dummy.output.DummyOutput",
        "file_input": "logprep.connector.file.input.FileInput",
        "http_input": "logprep.connector.http.input.HttpInput",
        "http_output": "logprep.connector.http.output.HttpOutput",
        "http_generator_output": "logprep.generator.http.output.HttpGeneratorOutput",
        "json_input": "logprep.connector.json.input.JsonInput",
        "jsonl_input": "logprep.connector.jsonl.input.JsonlInput",
        "jsonl_output": "logprep.connector.jsonl.output.JsonlOutput",
        "opensearch_output": "logprep.connector.opensearch.output.OpensearchOutput",
        "s3_output": "logprep.connector.s3.output.S3Output",
    }

    _ng_mapping: ComponentTypeMap = {
        # Processors
        "amides": "logprep.ng.processor.amides.processor.Amides",
        "calculator": "logprep.ng.processor.calculator.processor.Calculator",
        "clusterer": "logprep.ng.processor.clusterer.processor.Clusterer",
        "concatenator": "logprep.ng.processor.concatenator.processor.Concatenator",
        "datetime_extractor": "logprep.ng.processor.datetime_extractor.processor.DatetimeExtractor",
        "decoder": "logprep.ng.processor.decoder.processor.Decoder",
        "deduplicator": "logprep.ng.processor.deduplicator.processor.Deduplicator",
        "deleter": "logprep.ng.processor.deleter.processor.Deleter",
        "dissector": "logprep.ng.processor.dissector.processor.Dissector",
        "domain_label_extractor": "logprep.ng.processor.domain_label_extractor.processor.DomainLabelExtractor",
        "domain_resolver": "logprep.ng.processor.domain_resolver.processor.DomainResolver",
        "dropper": "logprep.ng.processor.dropper.processor.Dropper",
        "field_manager": "logprep.ng.processor.field_manager.processor.FieldManager",
        "generic_adder": "logprep.ng.processor.generic_adder.processor.GenericAdder",
        "generic_resolver": "logprep.ng.processor.generic_resolver.processor.GenericResolver",
        "geoip_enricher": "logprep.ng.processor.geoip_enricher.processor.GeoipEnricher",
        "grokker": "logprep.ng.processor.grokker.processor.Grokker",
        "ip_informer": "logprep.ng.processor.ip_informer.processor.IpInformer",
        "key_checker": "logprep.ng.processor.key_checker.processor.KeyChecker",
        "labeler": "logprep.ng.processor.labeler.processor.Labeler",
        "list_comparison": "logprep.ng.processor.list_comparison.processor.ListComparison",
        "network_comparison": "logprep.ng.processor.network_comparison.processor.NetworkComparison",
        "pre_detector": "logprep.ng.processor.pre_detector.processor.PreDetector",
        "pseudonymizer": "logprep.ng.processor.pseudonymizer.processor.Pseudonymizer",
        "replacer": "logprep.ng.processor.replacer.processor.Replacer",
        "requester": "logprep.ng.processor.requester.processor.Requester",
        "selective_extractor": "logprep.ng.processor.selective_extractor.processor.SelectiveExtractor",
        "string_splitter": "logprep.ng.processor.string_splitter.processor.StringSplitter",
        "template_replacer": "logprep.ng.processor.template_replacer.processor.TemplateReplacer",
        "timestamp_differ": "logprep.ng.processor.timestamp_differ.processor.TimestampDiffer",
        "timestamper": "logprep.ng.processor.timestamper.processor.Timestamper",
        # Connectors
        "confluentkafka_input": "logprep.ng.connector.confluent_kafka.input.ConfluentKafkaInput",
        "confluentkafka_output": "logprep.ng.connector.confluent_kafka.output.ConfluentKafkaOutput",
        "console_output": "logprep.ng.connector.console.output.ConsoleOutput",
        "dummy_input": "logprep.ng.connector.dummy.input.DummyInput",
        "dummy_output": "logprep.ng.connector.dummy.output.DummyOutput",
        "file_input": "logprep.ng.connector.file.input.FileInput",
        "http_input": "logprep.ng.connector.http.input.HttpInput",
        "json_input": "logprep.ng.connector.json.input.JsonInput",
        "jsonl_input": "logprep.ng.connector.jsonl.input.JsonlInput",
        "jsonl_output": "logprep.ng.connector.jsonl.output.JsonlOutput",
        "opensearch_output": "logprep.ng.connector.opensearch.output.OpensearchOutput",
    }
    # pylint: enable=line-too-long

    _mapping: ComponentTypeMap = _non_ng_mapping
    _resolved_classes: dict[str, type[Processor | Connector | NgProcessor | NgConnector]] = {}

    @classmethod
    def set_ng_active(cls, ng_active: bool) -> None:
        """Replaces the non-ng mapping with the ng mapping and clears the resolved class cache."""
        cls._mapping = cls._ng_mapping if ng_active else cls._non_ng_mapping
        cls._resolved_classes.clear()

    @classmethod
    def get_classes(cls) -> dict[str, type[Processor | Connector | NgProcessor | NgConnector]]:
        """Get a dict of all mapped component type names and they class types."""
        return {component_type: cls.get_class(component_type) for component_type in cls._mapping}

    @classmethod
    def get_class(
        cls, component_type: str
    ) -> type[Processor | Connector | NgProcessor | NgConnector]:
        """Return the component class for a given type."""
        cached = cls._resolved_classes.get(component_type)
        if cached is not None:
            return cached

        dotted_path = cls._mapping.get(component_type)
        if dotted_path is None:
            raise ValueError(f"Unknown component type: {component_type}")

        resolved = _import_class(dotted_path)
        cls._resolved_classes[component_type] = resolved
        return resolved

    @classmethod
    def get_rule_class_by_rule_definition(cls, rule_definition: dict) -> type[Rule]:
        """Return the rule class for a given rule definition.

        Parameters
        ----------
        rule_definition : dict
            the rule definition dict, expected to contain a processor type key

        Returns
        -------
        type[Rule]
            The class of the rule

        Raises
        ------
        ValueError
            if the rule type is unknown or not set in the processor
        """
        processor_type = {elem for elem in rule_definition if elem in cls._mapping}
        if not processor_type:
            raise ValueError("Unknown rule type")
        processor_type = processor_type.pop()
        if not isinstance(processor_type, str):
            raise ValueError("Unknown rule type")
        processor_class = cls.get_class(processor_type)
        if not issubclass(processor_class, (Processor, NgProcessor)):
            # TODO after ng integration: remove
            raise ValueError(f"Unknown processor type: {processor_type}")
        rule_class = processor_class.rule_class
        if rule_class is None:
            raise ValueError(f"Rule type not set in processor: {processor_type}")
        return rule_class
