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
from multiprocessing import current_process
from typing import List, Tuple
from logging import Logger
from zipfile import ZipFile
from pathlib import Path
from functools import lru_cache, _lru_cache_wrapper
import joblib

from attr import define, field, validators

from logprep.abc.processor import Processor
from logprep.metrics.metric import calculate_new_average
from logprep.processor.amides.rule import AmidesRule
from logprep.processor.amides.detection import MisuseDetector, RuleAttributor
from logprep.processor.amides.normalize import CommandLineNormalizer
from logprep.util.helper import get_dotted_field_value
from logprep.util.getter import GetterFactory


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

        max_cache_entries: int = field(default=1048576, validator=validators.instance_of(int))
        """Maximum number of cached command-lines and their classification results."""
        decision_threshold: float = field(validator=validators.instance_of(float))
        """Specifies the decision threshold of the misuse detector to adjust it's overall
        classification performance."""
        num_rule_attributions: int = field(default=10, validator=validators.instance_of(int))
        """Number of rule attributions returned in case of a positive misuse detection result."""
        models_path: str = field(validator=validators.instance_of(str))
        """Path or URI of the archive (.zip) containing the models used by the misuse detector
        and the rule attributor."""

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

    __slots__ = (
        "_misuse_detector",
        "_rule_attributor",
        "_normalizer",
        "_evaluate_cmdline_cached",
    )

    _misuse_detector: MisuseDetector
    _rule_attributor: RuleAttributor
    _normalizer: CommandLineNormalizer
    _evaluate_cmdline_cached: _lru_cache_wrapper

    rule_class = AmidesRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.metrics = self.AmidesMetrics(
            labels=self.metric_labels,
            generic_rule_tree=self._generic_tree.metrics,
            specific_rule_tree=self._specific_tree.metrics,
        )
        self._normalizer = CommandLineNormalizer(max_num_values_length=3, max_str_length=30)
        self._evaluate_cmdline_cached = lru_cache(maxsize=self._config.max_cache_entries)(
            self._evaluate_cmdline
        )

    def setup(self):
        models = self._load_and_unpack_models()

        self._misuse_detector = MisuseDetector(models["single"], self._config.decision_threshold)
        self._rule_attributor = RuleAttributor(
            models["multi"],
            self._config.num_rule_attributions,
        )

    def _load_and_unpack_models(self):
        if not Path(self._config.models_path).exists():
            self._logger.debug("Getting AMIDES models archive...")
            models_archive = Path(f"{current_process().name}-{self.name}.zip")
            models_archive.touch()
            models_archive.write_bytes(
                GetterFactory.from_string(str(self._config.models_path)).get_raw()
            )
            self._logger.debug("Finished getting AMIDES models archive...")
            self._config.models_path = str(models_archive.absolute())

        with ZipFile(self._config.models_path, mode="r") as zip_file:
            with zip_file.open("model", mode="r") as models_file:
                models = joblib.load(models_file)

        return models

    def _apply_rules(self, event: dict, rule: AmidesRule):
        cmdline = get_dotted_field_value(event, rule.source_fields[0])
        if not cmdline:
            return

        self.metrics.total_cmdlines += 1

        normalized = self._normalizer.normalize(cmdline)
        if not normalized:
            return

        result = self._evaluate_cmdline_cached(normalized)
        self._update_cache_metrics()

        if result:
            self._write_target_field(event=event, rule=rule, result=result)

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

    def _update_cache_metrics(self):
        cache_info = self._evaluate_cmdline_cached.cache_info()
        self.metrics.new_results = cache_info.misses
        self.metrics.cached_results = cache_info.hits
        self.metrics.num_cache_entries = cache_info.currsize
        self.metrics.cache_load = cache_info.currsize / cache_info.maxsize
