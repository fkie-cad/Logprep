# pylint: disable=import-outside-toplevel
"""module for component registry
    it is used to check if a component is known to the system.
    You have to register new components here by adding their import path and the corresponding class
    to the mappings 'processors' or 'connectors'.
"""


class Registry:
    """Component Registry"""

    processors = {
        "calculator": ("logprep.processor.calculator.processor", "Calculator"),
        "clusterer": ("logprep.processor.clusterer.processor", "Clusterer"),
        "concatenator": ("logprep.processor.concatenator.processor", "Concatenator"),
        "datetime_extractor": (
            "logprep.processor.datetime_extractor.processor",
            "DatetimeExtractor",
        ),
        "deleter": ("logprep.processor.deleter.processor", "Deleter"),
        "dissector": ("logprep.processor.dissector.processor", "Dissector"),
        "domain_label_extractor": (
            "logprep.processor.domain_label_extractor.processor",
            "DomainLabelExtractor",
        ),
        "domain_resolver": ("logprep.processor.domain_resolver.processor", "DomainResolver"),
        "dropper": ("logprep.processor.dropper.processor", "Dropper"),
        "field_manager": ("logprep.processor.field_manager.processor", "FieldManager"),
        "generic_adder": ("logprep.processor.generic_adder.processor", "GenericAdder"),
        "generic_resolver": ("logprep.processor.generic_resolver.processor", "GenericResolver"),
        "geoip_enricher": ("logprep.processor.geoip_enricher.processor", "GeoipEnricher"),
        "hyperscan_resolver": (
            "logprep.processor.hyperscan_resolver.processor",
            "HyperscanResolver",
        ),
        "ip_informer": ("logprep.processor.ip_informer.processor", "IpInformer"),
        "key_checker": ("logprep.processor.key_checker.processor", "KeyChecker"),
        "labeler": ("logprep.processor.labeler.processor", "Labeler"),
        "list_comparison": ("logprep.processor.list_comparison.processor", "ListComparison"),
        "normalizer": ("logprep.processor.normalizer.processor", "Normalizer"),
        "pre_detector": ("logprep.processor.pre_detector.processor", "PreDetector"),
        "pseudonymizer": ("logprep.processor.pseudonymizer.processor", "Pseudonymizer"),
        "requester": ("logprep.processor.requester.processor", "Requester"),
        "selective_extractor": (
            "logprep.processor.selective_extractor.processor",
            "SelectiveExtractor",
        ),
        "string_splitter": ("logprep.processor.string_splitter.processor", "StringSplitter"),
        "template_replacer": ("logprep.processor.template_replacer.processor", "TemplateReplacer"),
        "timestamp_differ": ("logprep.processor.timestamp_differ.processor", "TimestampDiffer"),
    }

    connectors = {
        "json_input": ("logprep.connector.json.input", "JsonInput"),
        "jsonl_input": ("logprep.connector.jsonl.input", "JsonlInput"),
        "file_input": ("logprep.connector.file.input", "FileInput"),
        "dummy_input": ("logprep.connector.dummy.input", "DummyInput"),
        "dummy_output": ("logprep.connector.dummy.output", "DummyOutput"),
        "confluentkafka_input": ("logprep.connector.confluent_kafka.input", "ConfluentKafkaInput"),
        "confluentkafka_output": (
            "logprep.connector.confluent_kafka.output",
            "ConfluentKafkaOutput",
        ),
        "console_output": ("logprep.connector.console.output", "ConsoleOutput"),
        "elasticsearch_output": ("logprep.connector.elasticsearch.output", "ElasticsearchOutput"),
        "jsonl_output": ("logprep.connector.jsonl.output", "JsonlOutput"),
        "opensearch_output": ("logprep.connector.opensearch.output", "OpensearchOutput"),
        "http_input": ("logprep.connector.http.input", "HttpConnector"),
    }

    mapping = processors | connectors

    @classmethod
    def get_class(cls, component_type):
        """return the component class for a given type

        Parameters
        ----------
        component_type : str
            the component type

        Returns
        -------
        _type_
            _description_
        """
        module_class_tuple = cls.mapping.get(component_type)
        component_module = __import__(module_class_tuple[0], fromlist=[module_class_tuple[1]])
        return getattr(component_module, module_class_tuple[1])
