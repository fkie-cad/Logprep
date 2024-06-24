"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The predetector requires the additional field :code:`pre_detector`.

The rule fields and a `pre_detector_id` are written into a custom output
of the current output connector.
The `pre_detector_id` will be furthermore added to the triggering event
so that an event can be linked with its detection.

The following example shows a complete rule:

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: "very malicious!"'
    pre_detector:
      case_condition: directly
      id: RULE_ONE_ID
      mitre:
      - attack.something1
      - attack.something2
      severity: critical
      title: Rule one
    description: Some malicious event.

Applying this rule to the event

..  code-block:: json
    :linenos:
    :caption: Example Input Event

    {
      "some_field": "very malicious!",
    }

would result in the following output and event enrichment

..  code-block:: json
    :linenos:
    :caption: Enriched event

    {
      "some_field": "very malicious!",
      "pre_detection_id": "80bfea3f-c24e-41d0-b82d-b2f02fc03ba9"
    }

..  code-block:: json
    :linenos:
    :caption: Generated extra output

    {
      "@timestamp": "2023-06-16T08:23:41.000Z",
      "id": "RULE_ONE_ID",
      "title": "Rule one",
      "mitre": ["attack.something1", "attack.something2"],
      "case_condition": "directly",
      "rule_filter": "(some_field: 'very malicious!')",
      "severity": "critical",
      "pre_detection_id": "80bfea3f-c24e-41d0-b82d-b2f02fc03ba9",
      "description": "Some malicious event."
    }

This generated extra output contains a corresponding :code:`rule_filter` in lucene notation, which
can be used to further investigate this rule in an existing OpenSearch or ElasticSearch.

Additionally, the optional field :code:`ip_fields` can be specified.
It allows to specify a list of fields that can be compared to a list of IPs,
which can be configured in the pipeline for the predetector.
If this field was specified, then the rule will *only* trigger in case one of
the IPs from the list is also available in the specified fields.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: 'some_field: something AND some_ip_field'
    pre_detector:
      id: RULE_ONE_ID
      title: Rule one
      severity: critical
      mitre:
      - some_tag
      case_condition: directly
    description: Some malicous event.
    ip_fields:
    - some_ip_field

.. autoclass:: logprep.processor.pre_detector.rule.PreDetectorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from functools import cached_property
from typing import Optional, Union

from attrs import asdict, define, field, validators

from logprep.processor.base.rule import Rule


class PreDetectorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):  # pylint: disable=too-many-instance-attributes
        """RuleConfig for Predetector"""

        id: str = field(validator=validators.instance_of((str, int)))
        """An ID for the triggered rule."""
        title: str = field(validator=validators.instance_of(str))
        """A description for the triggered rule."""
        severity: str = field(validator=validators.instance_of(str))
        """Rating how dangerous an Event is, i.e. `critical`."""
        mitre: list = field(validator=validators.instance_of(list))
        """A list of MITRE ATT&CK tags."""
        case_condition: str = field(validator=validators.instance_of(str))
        """The type of the triggered rule, mostly `directly`."""
        ip_fields: list = field(validator=validators.instance_of(list), factory=list)
        """Specify a list of fields that can be compared to a list of IPs,
        which can be configured in the pipeline for the predetector.
        If this field was specified, then the rule will *only* trigger in case one of
        the IPs from the list is also available in the specified fields."""
        sigma_fields: Union[list, bool] = field(
            validator=validators.instance_of((list, bool)), factory=list
        )
        """tbd"""
        link: Optional[str] = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """A link to the rule if applicable."""

    def __eq__(self, other: "PreDetectorRule") -> bool:
        return all(
            [
                super().__eq__(other),
                self.ip_fields == other.ip_fields,
            ]
        )

    # pylint: disable=C0111
    @cached_property
    def detection_data(self) -> dict:
        detection_data = asdict(
            self._config, filter=lambda attribute, _: attribute.name not in self.special_field_types
        )
        if self._config.link is None:
            del detection_data["link"]
        return detection_data

    @property
    def ip_fields(self) -> list:
        return self._config.ip_fields

    @property
    def description(self) -> str:
        return self._config.description

    # pylint: enable=C0111
