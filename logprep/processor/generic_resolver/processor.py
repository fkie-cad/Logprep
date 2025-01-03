"""
GenericResolver
===============

The `generic_resolver` resolves log event values using regex lists.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - genericresolvername:
        type: generic_resolver
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.generic_resolver.processor.GenericResolver.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.generic_resolver.rule
"""

from functools import cached_property, lru_cache
from typing import Optional

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.metrics.metrics import GaugeMetric
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.helper import add_fields_to, get_dotted_field_value


class GenericResolver(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """GenericResolver config"""

        max_cache_entries: Optional[int] = field(
            validator=validators.optional(validators.instance_of(int)), default=0
        )
        """(Optional) Size of cache for results when resolving form a list.
        The cache can be disabled by setting it this option to :code:`0`."""
        cache_metrics_interval: Optional[int] = field(
            validator=validators.optional(validators.instance_of(int)), default=1
        )
        """(Optional) Cache metrics won't be updated immediately.
        Instead updating is skipped for a number of events before it's next update.
        :code:`cache_metrics_interval` sets the number of events between updates (default: 1)."""

    @define(kw_only=True)
    class Metrics(FieldManager.Metrics):
        """Tracks statistics about the generic resolver"""

        new_results: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of newly resolved values",
                name="generic_resolver_new_results",
            )
        )
        """Number of newly resolved values"""

        cached_results: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of values resolved from cache",
                name="generic_resolver_cached_results",
            )
        )
        """Number of resolved values from cache"""
        num_cache_entries: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of resolved values in cache",
                name="generic_resolver_num_cache_entries",
            )
        )
        """Number of values in cache"""
        cache_load: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Relative cache load.",
                name="generic_resolver_cache_load",
            )
        )
        """Relative cache load."""

    __slots__ = ["_cache_metrics_skip_count"]

    _cache_metrics_skip_count: int

    rule_class = GenericResolverRule

    @property
    def max_cache_entries(self):
        """Returns the configured number of max_cache_entries"""
        return self._config.max_cache_entries

    @property
    def cache_metrics_interval(self):
        """Returns the configured cache_metrics_interval"""
        return self._config.cache_metrics_interval

    @cached_property
    def _get_lru_cached_value_from_list(self):
        """Returns lru cashed method to retrieve values from list if configured"""
        if self.max_cache_entries <= 0:
            return self._resolve_value_from_list
        return lru_cache(maxsize=self.max_cache_entries)(self._resolve_value_from_list)

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        source_field_values = [
            get_dotted_field_value(event, source_field)
            for source_field in rule.field_mapping.keys()
        ]
        self._handle_missing_fields(event, rule, rule.field_mapping.keys(), source_field_values)
        conflicting_fields = []
        for source_field, target_field in rule.field_mapping.items():
            source_field_value = get_dotted_field_value(event, source_field)
            if source_field_value is None:
                continue
            content = self._find_content_of_first_matching_pattern(rule, source_field_value)
            if not content:
                continue
            current_content = get_dotted_field_value(event, target_field)
            if isinstance(current_content, list) and content in current_content:
                continue
            if rule.merge_with_target and current_content is None:
                content = [content]
            try:
                add_fields_to(
                    event,
                    fields={target_field: content},
                    rule=rule,
                    merge_with_target=rule.merge_with_target,
                    overwrite_target=rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)

        self._update_cache_metrics()

        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

    def _find_content_of_first_matching_pattern(self, rule, source_field_value):
        if rule.resolve_from_file:
            replacements = rule.resolve_from_file["additions"]
            matches = rule.pattern.match(source_field_value)
            if matches:
                mapping = matches.group("mapping")
                if rule.ignore_case:
                    mapping = mapping.upper()
                content = replacements.get(mapping)
                if content:
                    return content
        return self._get_lru_cached_value_from_list(rule, source_field_value)

    def _resolve_value_from_list(
        self, rule: GenericResolverRule, source_field_value: str
    ) -> Optional[str]:
        for pattern, content in rule.compiled_resolve_list:
            if pattern.search(source_field_value):
                return content

    def _update_cache_metrics(self):
        if self.max_cache_entries <= 0:
            return
        self._cache_metrics_skip_count += 1
        if self._cache_metrics_skip_count < self.cache_metrics_interval:
            return
        self._cache_metrics_skip_count = 0

        cache_info = self._get_lru_cached_value_from_list.cache_info()
        self.metrics.new_results += cache_info.misses
        self.metrics.cached_results += cache_info.hits
        self.metrics.num_cache_entries += cache_info.currsize
        self.metrics.cache_load += cache_info.currsize / cache_info.maxsize

    def setup(self):
        super().setup()
        self._cache_metrics_skip_count = 0
