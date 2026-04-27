"""
Labeler
=======

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^

..  code-block:: yaml
    :linenos:

    - labelername:
        type: labeler
        schema: tests/testdata/labeler_rules/labeling/schema.json
        include_parent_labels: true
        rules:
            - tests/testdata/labeler_rules/rules

.. autoclass:: logprep.processor.labeler.processor.Labeler.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.labeler.rule
"""

import typing
from collections.abc import Iterable, Sequence

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.base.rule import Rule
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule
from logprep.util.helper import add_fields_to, get_dotted_field_value


class Labeler(Processor):
    """Processor used to label log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Labeler Configurations"""

        schema: str = field(validator=validators.instance_of(str))
        """Path to a labeling schema file. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: Processor - Labeler Schema File Memory Consumption

           Be aware that all values of the remote file were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Labeler Schema File Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """
        include_parent_labels: bool = field(default=False, validator=validators.instance_of(bool))
        """If the option is deactivated only labels defined in a rule will be activated.
        Otherwise, also allowed labels in the path to the *root* of the corresponding category
        of a label will be added.
        This allows to search for higher level labels if this option was activated in the rule.
        """

    __slots__ = ["_schema", "_include_parent_labels"]

    _schema: LabelingSchema

    rule_class = LabelerRule

    def __init__(self, name: str, configuration: "Labeler.Config"):
        self._schema = LabelingSchema.create_from_file(configuration.schema)
        super().__init__(name, configuration=configuration)

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(Labeler.Config, self._config)

    @property
    def rules(self) -> Sequence[LabelerRule]:
        """Returns all rules"""
        return typing.cast(Sequence[LabelerRule], super().rules)

    def setup(self):
        super().setup()
        for rule in self.rules:
            if self._config.include_parent_labels:
                rule.add_parent_labels_from_schema(self._schema)
            rule.conforms_to_schema(self._schema)

    def _apply_rules(self, event: dict, rule: Rule) -> None:
        """Applies the rule to the current event"""
        rule = typing.cast(LabelerRule, rule)
        add_fields_to(event, rule.prefixed_label, rule=rule, merge_with_target=True)
        # we have already added (merged) the prefixed_labels with list values
        # now we extract them to make them unique and sorted
        fields = {
            key: sorted(set(typing.cast(Iterable, get_dotted_field_value(event, key))))
            for key, _ in rule.prefixed_label.items()
        }
        add_fields_to(event, fields, rule=rule, overwrite_target=True)
