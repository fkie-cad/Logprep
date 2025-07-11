"""module for processor registry
it is used to check if a processor is known to the system.
you have to register new processors here by import them and add to `ProcessorRegistry.mapping`
"""

from typing import Dict, Type

from logprep.abc.connector import Connector
from logprep.abc.processor import Processor
from logprep.connector.confluent_kafka.input import ConfluentKafkaInput
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.connector.console.output import ConsoleOutput
from logprep.connector.dummy.input import DummyInput
from logprep.connector.dummy.output import DummyOutput
from logprep.connector.file.input import FileInput
from logprep.connector.http.input import HttpInput
from logprep.connector.http.output import HttpOutput
from logprep.connector.json.input import JsonInput
from logprep.connector.jsonl.input import JsonlInput
from logprep.connector.jsonl.output import JsonlOutput
from logprep.connector.opensearch.output import OpensearchOutput
from logprep.connector.s3.output import S3Output
from logprep.generator.confluent_kafka.output import ConfluentKafkaGeneratorOutput
from logprep.generator.http.output import HttpGeneratorOutput
from logprep.ng.processor.amides.processor import Amides as NgAmides
from logprep.ng.processor.calculator.processor import Calculator as NGCalculator
from logprep.ng.processor.clusterer.processor import Clusterer as NgClusterer
from logprep.ng.processor.concatenator.processor import Concatenator as NgConcatenator
from logprep.ng.processor.datetime_extractor.processor import (
    DatetimeExtractor as NgDatetimeExtractor,
)
from logprep.ng.processor.deleter.processor import Deleter as NgDeleter
from logprep.ng.processor.dissector.processor import Dissector as NgDissector
from logprep.ng.processor.domain_label_extractor.processor import (
    DomainLabelExtractor as NgDomainLabelExtractor,
)
from logprep.ng.processor.domain_resolver.processor import (
    DomainResolver as NgDomainResolver,
)
from logprep.ng.processor.dropper.processor import Dropper as NgDropper
from logprep.ng.processor.field_manager.processor import FieldManager as NgFieldManager
from logprep.ng.processor.generic_adder.processor import GenericAdder as NgGenericAdder
from logprep.ng.processor.generic_resolver.processor import (
    GenericResolver as NgGenericResolver,
)
from logprep.ng.processor.geoip_enricher.processor import (
    GeoipEnricher as NgGeoipEnricher,
)
from logprep.ng.processor.grokker.processor import Grokker as NgGrokker
from logprep.ng.processor.ip_informer.processor import IpInformer as NgIpInformer
from logprep.ng.processor.key_checker.processor import KeyChecker as NgKeyChecker
from logprep.ng.processor.labeler.processor import Labeler as NgLabeler
from logprep.ng.processor.list_comparison.processor import (
    ListComparison as NgListComparison,
)
from logprep.ng.processor.pre_detector.processor import PreDetector as NgPreDetector
from logprep.ng.processor.pseudonymizer.processor import (
    Pseudonymizer as NgPseudonymizer,
)
from logprep.ng.processor.replacer.processor import Replacer as NgReplacer
from logprep.ng.processor.requester.processor import Requester as NgRequester
from logprep.ng.processor.selective_extractor.processor import (
    SelectiveExtractor as NGSelectiveExtractor,
)
from logprep.ng.processor.string_splitter.processor import (
    StringSplitter as NgStringSplitter,
)
from logprep.ng.processor.template_replacer.processor import (
    TemplateReplacer as NgTemplateReplacer,
)
from logprep.ng.processor.timestamp_differ.processor import (
    TimestampDiffer as NgTimestampDiffer,
)
from logprep.ng.processor.timestamper.processor import Timestamper as NgTimestamper
from logprep.processor.amides.processor import Amides
from logprep.processor.base.rule import Rule
from logprep.processor.calculator.processor import Calculator
from logprep.processor.clusterer.processor import Clusterer
from logprep.processor.concatenator.processor import Concatenator
from logprep.processor.datetime_extractor.processor import DatetimeExtractor
from logprep.processor.deleter.processor import Deleter
from logprep.processor.dissector.processor import Dissector
from logprep.processor.domain_label_extractor.processor import DomainLabelExtractor
from logprep.processor.domain_resolver.processor import DomainResolver
from logprep.processor.dropper.processor import Dropper
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.generic_adder.processor import GenericAdder
from logprep.processor.generic_resolver.processor import GenericResolver
from logprep.processor.geoip_enricher.processor import GeoipEnricher
from logprep.processor.grokker.processor import Grokker
from logprep.processor.ip_informer.processor import IpInformer
from logprep.processor.key_checker.processor import KeyChecker
from logprep.processor.labeler.processor import Labeler
from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.pre_detector.processor import PreDetector
from logprep.processor.pseudonymizer.processor import Pseudonymizer
from logprep.processor.replacer.processor import Replacer
from logprep.processor.requester.processor import Requester
from logprep.processor.selective_extractor.processor import SelectiveExtractor
from logprep.processor.string_splitter.processor import StringSplitter
from logprep.processor.template_replacer.processor import TemplateReplacer
from logprep.processor.timestamp_differ.processor import TimestampDiffer
from logprep.processor.timestamper.processor import Timestamper


class Registry:
    """Component Registry"""

    mapping: Dict[str, Type[Processor | Connector]] = {
        # Processors
        "amides": Amides,
        "calculator": Calculator,
        "clusterer": Clusterer,
        "concatenator": Concatenator,
        "datetime_extractor": DatetimeExtractor,
        "deleter": Deleter,
        "dissector": Dissector,
        "domain_label_extractor": DomainLabelExtractor,
        "domain_resolver": DomainResolver,
        "dropper": Dropper,
        "field_manager": FieldManager,
        "generic_adder": GenericAdder,
        "generic_resolver": GenericResolver,
        "geoip_enricher": GeoipEnricher,
        "grokker": Grokker,
        "ip_informer": IpInformer,
        "key_checker": KeyChecker,
        "labeler": Labeler,
        "list_comparison": ListComparison,
        "ng_amides": NgAmides,
        "ng_calculator": NGCalculator,
        "ng_clusterer": NgClusterer,
        "ng_concatenator": NgConcatenator,
        "ng_deleter": NgDeleter,
        "ng_datetime_extractor": NgDatetimeExtractor,
        "ng_dissector": NgDissector,
        "ng_domain_label_extractor": NgDomainLabelExtractor,
        "ng_domain_resolver": NgDomainResolver,
        "ng_dropper": NgDropper,
        "ng_field_manager": NgFieldManager,
        "ng_generic_adder": NgGenericAdder,
        "ng_generic_resolver": NgGenericResolver,
        "ng_geoip_enricher": NgGeoipEnricher,
        "ng_grokker": NgGrokker,
        "ng_ip_informer": NgIpInformer,
        "ng_key_checker": NgKeyChecker,
        "ng_labeler": NgLabeler,
        "ng_list_comparison": NgListComparison,
        "ng_replacer": NgReplacer,
        "ng_requester": NgRequester,
        "ng_string_splitter": NgStringSplitter,
        "ng_template_replacer": NgTemplateReplacer,
        "ng_timestamp_differ": NgTimestampDiffer,
        "ng_timestamper": NgTimestamper,
        "ng_pre_detector": NgPreDetector,
        "ng_pseudonymizer": NgPseudonymizer,
        "ng_selective_extractor": NGSelectiveExtractor,
        "pre_detector": PreDetector,
        "pseudonymizer": Pseudonymizer,
        "requester": Requester,
        "replacer": Replacer,
        "selective_extractor": SelectiveExtractor,
        "string_splitter": StringSplitter,
        "template_replacer": TemplateReplacer,
        "timestamp_differ": TimestampDiffer,
        "timestamper": Timestamper,
        # Connectors
        "json_input": JsonInput,
        "jsonl_input": JsonlInput,
        "file_input": FileInput,
        "dummy_input": DummyInput,
        "dummy_output": DummyOutput,
        "confluentkafka_input": ConfluentKafkaInput,
        "confluentkafka_output": ConfluentKafkaOutput,
        "console_output": ConsoleOutput,
        "jsonl_output": JsonlOutput,
        "opensearch_output": OpensearchOutput,
        "http_input": HttpInput,
        "http_output": HttpOutput,
        "http_generator_output": HttpGeneratorOutput,
        "confluentkafka_generator_output": ConfluentKafkaGeneratorOutput,
        "s3_output": S3Output,
    }

    @classmethod
    def get_class(cls, component_type: str) -> Type[Processor | Connector]:
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
        processor_class = cls.mapping.get(component_type)
        if processor_class is None:
            raise ValueError(f"Unknown processor type: {component_type}")
        return processor_class

    @classmethod
    def get_rule_class_by_rule_definition(cls, rule_definition: dict) -> Type[Rule]:
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
        if not issubclass(processor_class, Processor):
            raise ValueError(f"Unknown processor type: {processor_type}")
        rule_class = processor_class.rule_class
        if rule_class is None:
            raise ValueError(f"Rule type not set in processor: {processor_type}")
        return rule_class
