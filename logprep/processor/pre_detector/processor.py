"""
PreDetector
===========

The `pre_detector` is a processor that creates alerts for matching events. It adds MITRE ATT&CK
data to the alerts.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - predetectorname:
        type: pre_detector
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        outputs:
            - kafka: sre_topic
        alert_ip_list_path: /tmp/ip_list.yml

.. autoclass:: logprep.processor.pre_detector.processor.PreDetector.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.pre_detector.rule
"""

from functools import cached_property
from uuid import uuid4

from attr import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.pre_detector.ip_alerter import IPAlerter
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util.helper import get_dotted_field_value, add_field_to
from logprep.util.time import TimeParser


class PreDetector(Processor):
    """Processor used to pre_detect log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """PreDetector config"""

        outputs: tuple[dict[str, str]] = field(
            validator=[
                validators.deep_iterable(
                    member_validator=[
                        validators.instance_of(dict),
                        validators.deep_mapping(
                            key_validator=validators.instance_of(str),
                            value_validator=validators.instance_of(str),
                            mapping_validator=validators.max_len(1),
                        ),
                    ],
                    iterable_validator=validators.instance_of(tuple),
                ),
                validators.min_len(1),
            ],
            converter=tuple,
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""

        alert_ip_list_path: str = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )
        """
        Path to a YML file or a list of paths to YML files with dictionaries of IPs.
        For string format see :ref:`getters`.
        It is used by the Predetector to throw alerts if one of the IPs is found
        in fields that were defined in a rule.

        It uses IPs or networks in the CIDR format as keys and can contain expiration
        dates in the ISO format as values.
        If a value is empty, then there is no expiration date for the IP check.
        If a checked IP is covered by an IP and a network in the dictionary
        (i.e. IP 127.0.0.1 and network 127.0.0.0/24 when checking 127.0.0.1),
        then the expiration date of the IP is being used.
        """

    rule_class = PreDetectorRule

    @cached_property
    def _ip_alerter(self):
        return IPAlerter(self._config.alert_ip_list_path)

    def _apply_rules(self, event, rule):
        if not (
            self._ip_alerter.has_ip_fields(rule)
            and not self._ip_alerter.is_in_alerts_list(rule, event)
        ):
            self._get_detection_result(event, rule)
        for detection, _ in self._extra_data:
            detection["creation_timestamp"] = TimeParser.now().isoformat()
            timestamp = get_dotted_field_value(event, "@timestamp")
            if timestamp is not None:
                detection["@timestamp"] = timestamp

    def _get_detection_result(self, event: dict, rule: PreDetectorRule):
        pre_detection_id = get_dotted_field_value(event, "pre_detection_id")
        if pre_detection_id is None:
            pre_detection_id = str(uuid4())
            add_field_to(event, "pre_detection_id", pre_detection_id)

        detection_result = self._generate_detection_result(pre_detection_id, event, rule)
        self._extra_data.append((detection_result, self._config.outputs))

    @staticmethod
    def _generate_detection_result(pre_detection_id: str, event: dict, rule: PreDetectorRule):
        detection_result = rule.detection_data
        detection_result["rule_filter"] = rule.filter_str
        detection_result["description"] = rule.description
        detection_result["pre_detection_id"] = pre_detection_id

        host_name = get_dotted_field_value(event, "host.name")
        if host_name is not None:
            detection_result["host"] = {"name": host_name}
        return detection_result
