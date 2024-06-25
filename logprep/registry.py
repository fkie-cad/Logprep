"""module for processor registry
    it is used to check if a processor is known to the system.
    you have to register new processors here by import them and add to `ProcessorRegistry.mapping`
"""

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
from logprep.processor.amides.processor import Amides
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
from logprep.processor.hyperscan_resolver.processor import HyperscanResolver
from logprep.processor.ip_informer.processor import IpInformer
from logprep.processor.key_checker.processor import KeyChecker
from logprep.processor.labeler.processor import Labeler
from logprep.processor.list_comparison.processor import ListComparison
from logprep.processor.pre_detector.processor import PreDetector
from logprep.processor.pseudonymizer.processor import Pseudonymizer
from logprep.processor.requester.processor import Requester
from logprep.processor.selective_extractor.processor import SelectiveExtractor
from logprep.processor.string_splitter.processor import StringSplitter
from logprep.processor.template_replacer.processor import TemplateReplacer
from logprep.processor.timestamp_differ.processor import TimestampDiffer
from logprep.processor.timestamper.processor import Timestamper


class Registry:
    """Component Registry"""

    mapping = {
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
        "hyperscan_resolver": HyperscanResolver,
        "ip_informer": IpInformer,
        "key_checker": KeyChecker,
        "labeler": Labeler,
        "list_comparison": ListComparison,
        "pre_detector": PreDetector,
        "pseudonymizer": Pseudonymizer,
        "requester": Requester,
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
        "s3_output": S3Output,
    }

    @classmethod
    def get_class(cls, component_type):
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
        return cls.mapping.get(component_type)
