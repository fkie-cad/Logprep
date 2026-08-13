"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The field name replacer requires the additional field :code:`field_name_replacer`.
It changes configured text in dictionary keys below the fields listed in
:code:`field_name_replacer.source_fields`. This can make field names usable in
systems that do not allow characters such as dots in keys.

In the following example, the key :code:`k8s.application/kind` below
:code:`test` is changed to :code:`k8s__application/kind`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: test
    field_name_replacer:
      source_fields:
        - test
      to_replace: "."
      replacement: "__"

Keys in nested dictionaries and dictionaries in lists are changed recursively
as well.

If changing a key would create a key that already exists,
:code:`field_name_replacer.collision_strategy` controls the outcome. The
default, :code:`raise`, reports an error. :code:`keep_incoming` keeps the
value from the key changed by the processor. :code:`merge` combines compatible
values. When merging dictionaries, values from keys changed by the processor
take precedence over values already present at the resulting key. When merging
lists, the items already present at the resulting key precede the items from
the changed key. A list can also be combined with a scalar; other incompatible
values report an error.

The following rule changes :code:`service.name` to :code:`service__name`,
which already exists, and merges their dictionary values. If both source
dictionaries contain the same key, the value below :code:`service.name` takes
precedence.

..  code-block:: yaml
    :linenos:
    :caption: Resolve a renamed-key collision by merging

    filter: test
    field_name_replacer:
      source_fields:
        - test
      to_replace: "."
      replacement: "__"
      collision_strategy: merge

.. autoclass:: logprep.processor.field_name_replacer.rule.FieldNameReplacerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for field_name_replacer:
---------------------------------

.. datatemplate:import-module:: tests.unit.processor.field_name_replacer.test_field_name_replacer
   :template: testcase-renderer.tmpl
"""

import re
import typing
from collections.abc import Callable
from enum import Enum
from functools import cached_property

from attr import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule
from logprep.util.helper import (
    FieldCollisionError,
    FieldValue,
    keep_incoming_collision_handler,
    merge_mutating_collision_handler,
)


class CollisionStrategy(Enum):
    KEEP_INCOMING = "keep_incoming"
    MERGE = "merge"
    RAISE = "raise"


class FieldNameReplacerRule(Rule):
    """Configure how field names are changed in selected event fields."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Configuration for a FieldNameReplacer rule."""

        collision_strategy: CollisionStrategy = field(
            validator=validators.instance_of(CollisionStrategy),
            converter=CollisionStrategy,
            default=CollisionStrategy.RAISE,
        )
        """How to handle keys that collide after replacement: :code:`raise` (the default)
        raises an error, :code:`keep_incoming` retains the incoming value, and :code:`merge`
        combines compatible dictionaries and lists."""

        source_fields: list[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.and_(
                    validators.instance_of(str), validators.min_len(1)
                ),
                iterable_validator=validators.instance_of(list),
            )
        )
        """Fields whose contained dictionary keys should be changed."""

        strip_prefix: bool = field(validator=validators.instance_of(bool), default=False)
        """Remove configured text at the beginning of a key. Defaults to :code:`False`."""

        strip_suffix: bool = field(validator=validators.instance_of(bool), default=False)
        """Remove configured text at the end of a key. Defaults to :code:`False`."""

        collapse_sequences: bool = field(validator=validators.instance_of(bool), default=False)
        """Replace a sequence of configured text once. Defaults to :code:`False`."""

        to_replace: list[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.and_(
                    validators.instance_of(str), validators.min_len(1)
                ),
                iterable_validator=validators.and_(
                    validators.instance_of(list), validators.min_len(1)
                ),
            ),
            converter=lambda x: sorted(x, key=len, reverse=True) if isinstance(x, list) else [x],
        )
        """Characters or strings to replace in dictionary keys. When configured items
        overlap, the longest item takes precedence."""

        replacement: str = field(validator=validators.instance_of(str))
        """Text that replaces each configured character or string."""

    @property
    def config(self) -> Config:
        """Return the rule configuration with its specific type."""
        return typing.cast(FieldNameReplacerRule.Config, self._config)

    @cached_property
    def collision_handler(self) -> Callable[[str, FieldValue, FieldValue], FieldValue]:
        """Return the collision handler selected by this rule's strategy."""
        match self.config.collision_strategy:
            case CollisionStrategy.KEEP_INCOMING:
                return keep_incoming_collision_handler
            case CollisionStrategy.MERGE:
                return merge_mutating_collision_handler
            case _:

                def inner(key: str, existing: FieldValue, incoming: FieldValue) -> FieldValue:
                    raise FieldCollisionError(key, type(existing), type(incoming))

                return inner

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)

        self._strip_func: Callable[[str], str] = self._create_strip_func()
        self._replace_func: Callable[[str], str] = self._create_replace_func()

    def _create_replace_func(self) -> Callable[[str], str]:
        if self.config.collapse_sequences:
            alternatives = "|".join(re.escape(text) for text in self.config.to_replace)
            pattern = re.compile(rf"(?:{alternatives})+")

            return lambda value: pattern.sub(lambda _: self.config.replacement, value)
        else:

            def _replace_func(key: str) -> str:
                for ctr in self.config.to_replace:
                    key = key.replace(ctr, self.config.replacement)
                return key

            return _replace_func

    def _create_strip_func(self) -> Callable[[str], str]:
        alternatives = "|".join(re.escape(text) for text in self.config.to_replace)
        prefix_pattern: re.Pattern[str] | None = None
        suffix_pattern: re.Pattern[str] | None = None

        if self.config.strip_prefix:
            prefix_pattern = re.compile(rf"^(?:{alternatives})+")
        if self.config.strip_suffix:
            suffix_pattern = re.compile(rf"(?:{alternatives})+$")

        def _strip_func(value: str) -> str:
            if prefix_pattern is not None:
                value = prefix_pattern.sub("", value)
            if suffix_pattern is not None:
                value = suffix_pattern.sub("", value)
            return value

        return _strip_func

    def replace_key(self, key: str) -> str:
        """Return a key after applying the configured character replacements."""
        return self._replace_func(self._strip_func(key))
