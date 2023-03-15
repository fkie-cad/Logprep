"""
Adaptive Misuse Detection System (AMiDeS)
-----------------------------------------

The AMiDeS-processor performs Adaptive Misuse Detection on command-lines
of incoming process creation events. In case of a positive result, additional
rule attribution is performed.

Example
^^^^^^^

..  code-block:: yaml
    :linenos:

    - amides:
        type: amides
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        max_cache_entries: 10000
        decision_threshold: 0.0
        num_rule_attributions: 10
        models_path: /tmp/models.zip
"""
from time import time
from os.path import basename
from typing import List, Tuple
from logging import Logger
from zipfile import ZipFile
import joblib

from attr import define, field, validators

from logprep.abc.processor import Processor
from logprep.metrics.metric import calculate_new_average
from logprep.processor.amides.lru import LRUCache
from logprep.processor.amides.rule import AmidesRule
from logprep.processor.amides.detection import MisuseDetector, RuleAttributor
from logprep.processor.amides.normalize import CommandLineNormalizer
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import file_validator


class AmidesError(BaseException):
    """Default exception for all Amides-related errors."""

    def __init__(self, name: str, message: str):
        super().__init__(f"Amides ({name}): {message}")


class Amides(Processor):
    """Detects if incoming command-lines are malicious or not. Performs additional
    rule attribution in case of a malicious command-line."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Amides processor configuration class."""

        max_cache_entries: int = field(default=1000000, validator=validators.instance_of(int))
        """Maximum number of cached command-lines and their classification results."""
        decision_threshold: float = field(validator=validators.instance_of(float))
        """Specifies the decision threshold of the misuse detector to adjust it's overall
        classification performance."""
        num_rule_attributions: int = field(default=10, validator=validators.instance_of(int))
        """Number of rule attributions returned in case of a positive classification result."""
        models_path: str = field(validator=file_validator)
        """Path of the archive (.zip) containing the models used by the classifier."""

    @define(kw_only=True)
    class AmidesMetrics(Processor.ProcessorMetrics):
        """Track statistics specific for Amides instances."""

        total_cmdlines: int = 0
        """Total number of command-lines processed."""
        new_results: int = 0
        """Number of command-lines that triggered classification and rule attribution."""
        cached_results: int = 0
        """Number of command-lines that could be resolved from cache."""
        num_cache_entries: int = 0
        """Absolute number of current cache entries."""
        cache_load: float = 0.0
        """Relative cache load."""
        mean_misuse_detection_time: float = 0.0
        """Mean processing time of command-lines classified by the misuse detection model."""
        _mean_misuse_detection_time_sample_counter: int = 0
        mean_rule_attribution_time: float = 0.0
        """Mean processing time of command-lines classified by the rule attribution model."""
        _mean_rule_attribution_time_sample_counter: int = 0

        def update_mean_misuse_detection_time(self, new_sample):
            """Updates the mean processing time of the misuse detection."""
            new_mean, new_sample_counter = calculate_new_average(
                self.mean_misuse_detection_time,
                new_sample,
                self._mean_misuse_detection_time_sample_counter,
            )
            self.mean_misuse_detection_time = new_mean
            self._mean_misuse_detection_time_sample_counter = new_sample_counter

        def update_mean_rule_attribution_time(self, new_sample):
            """Updates the mean processing time of the rule attribution model."""
            new_mean, new_sample_counter = calculate_new_average(
                self.mean_rule_attribution_time,
                new_sample,
                self._mean_rule_attribution_time_sample_counter,
            )
            self.mean_rule_attribution_time = new_mean
            self._mean_rule_attribution_time_sample_counter = new_sample_counter

    __slots__ = ["_cache", "_misuse_detector", "_rule_attributor", "_normalizer"]

    _cache: LRUCache
    _misuse_detector: MisuseDetector
    _rule_attributor: RuleAttributor
    _normalizer: CommandLineNormalizer

    rule_class = AmidesRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.metrics = self.AmidesMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self._cache = LRUCache(max_items=self._config.max_cache_entries)
        self._normalizer = CommandLineNormalizer(max_num_values_length=3, max_str_length=30)
        self._setup_detectors()

    def _setup_detectors(self):
        models = self._load_models(self._config.models_path)

        self._misuse_detector = MisuseDetector(models["single"], self._config.decision_threshold)
        self._rule_attributor = RuleAttributor(
            models["multi"],
            self._config.num_rule_attributions,
        )

    def _load_models(self, path):
        models_filename = basename(path).rstrip(".zip")

        with ZipFile(path, mode="r") as zip_file:
            with zip_file.open(models_filename, mode="r") as models_file:
                models = joblib.load(models_file)

        return models

    def _apply_rules(self, event: dict, rule: AmidesRule):
        cmdline = get_dotted_field_value(event, rule.cmdline_field)
        if not cmdline:
            return

        self.metrics.total_cmdlines += 1

        normalized = self._normalizer.normalize(cmdline)
        if not normalized:
            return

        cached_result = self._cache.get(normalized)
        if cached_result is not None:
            result = cached_result
            self.metrics.cached_results += 1
        else:
            result = self._evaluate_cmdline(normalized)
            self._cache.insert(normalized, result)
            self.metrics.new_results += 1
            self.metrics.cache_load = self._cache.relative_load()
            self.metrics.num_cache_entries = self._cache.num_entries()

        if result:
            if not add_field_to(event, rule.rule_attributions_field, result):
                raise AmidesError(
                    self.name,
                    f"Rule attributions could not be added into '{rule.rule_attributions_field}'",
                )

    def _evaluate_cmdline(self, cmdline: str):
        result = self._perform_misuse_detection(cmdline)
        if result == 0:
            return []

        return self._calculate_rule_attributions(cmdline)

    def _perform_misuse_detection(self, cmdline: str) -> int:
        begin = time()
        result = self._misuse_detector.detect(cmdline)
        processing_time = time() - begin

        self.metrics.update_mean_misuse_detection_time(processing_time)

        return result

    def _calculate_rule_attributions(self, cmdline: str) -> List[Tuple[str, int]]:
        begin = time()
        attributions = self._rule_attributor.attribute(cmdline)
        processing_time = time() - begin

        self.metrics.update_mean_rule_attribution_time(processing_time)

        return attributions
