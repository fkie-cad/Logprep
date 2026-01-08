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
        rules:
            - tests/testdata/rules/rules
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

import typing
from functools import cached_property
from typing import cast
from uuid import uuid4

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.pre_detector.ip_alerter import IPAlerter
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util.helper import (
    FieldValue,
    add_fields_to,
    copy_fields_to_event,
    get_dotted_field_value,
)
from logprep.util.time import TimeParser, TimeParserException


class PreDetector(Processor):
    """Processor used to pre_detect log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """PreDetector config"""

        outputs: tuple[dict[str, str]] = field(
            validator=(
                validators.deep_iterable(
                    member_validator=(
                        validators.instance_of(dict),
                        validators.deep_mapping(
                            key_validator=validators.instance_of(str),
                            value_validator=validators.instance_of(str),
                            mapping_validator=validators.max_len(1),
                        ),
                    ),
                    iterable_validator=validators.instance_of(tuple),
                ),
                validators.min_len(1),
            ),
            converter=tuple,
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""

        alert_ip_list_path: str | None = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )
        """
        Path to a YML file or a list of paths to YML files with dictionaries of IPs.
        For string format see :ref:`getters`.
        It is used by the PreDetector to throw alerts if one of the IPs is found
        in fields that were defined in a rule.

        It uses IPs or networks in the CIDR format as keys and can contain expiration
        dates in the ISO format as values.
        If a value is empty, then there is no expiration date for the IP check.
        If a checked IP is covered by an IP and a network in the dictionary
        (i.e. IP 127.0.0.1 and network 127.0.0.0/24 when checking 127.0.0.1),
        then the expiration date of the IP is being used.

        .. security-best-practice::
           :title: Processor - PreDetector alert_ip_list_path Memory Consumption

           Be aware that all values of the remote file were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - PreDetector alert_ip_list_path Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.
        """

    rule_class = PreDetectorRule

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(PreDetector.Config, self._config)

    @cached_property
    def _ip_alerter(self) -> IPAlerter:
        return IPAlerter(self.config.alert_ip_list_path)

    def normalize_timestamp(self, rule: PreDetectorRule, timestamp: FieldValue) -> str:
        """method for normalizing the timestamp"""
        try:
            parsed_datetime = TimeParser.parse_datetime(
                cast(str, timestamp), rule.source_format, rule.source_timezone
            )
            return (
                parsed_datetime.astimezone(rule.target_timezone).isoformat().replace("+00:00", "Z")
            )
        except (TimeParserException, TypeError) as error:
            raise ProcessingWarning(
                "Could not parse timestamp",
                rule=rule,
                event=self.result.event,
                tags=["_pre_detector_timeparsing_failure"],
            ) from error

    def _apply_rules(self, event: dict, rule: PreDetectorRule):
        if not (
            self._ip_alerter.has_ip_fields(rule)
            and not self._ip_alerter.is_in_alerts_list(rule, event)
        ):
            self._get_detection_result(event, rule)
        for detection, _ in self.result.data:
            detection["creation_timestamp"] = TimeParser.now().isoformat()
            timestamp = get_dotted_field_value(event, rule.timestamp_field)
            if timestamp is not None:
                detection[rule.timestamp_field] = self.normalize_timestamp(rule, timestamp)

    def _get_detection_result(self, event: dict, rule: PreDetectorRule):
        pre_detection_id = get_dotted_field_value(event, "pre_detection_id")
        if pre_detection_id is None:
            pre_detection_id = str(uuid4())
            add_fields_to(event, {"pre_detection_id": pre_detection_id}, rule=rule)
        detection_result = self._generate_detection_result(pre_detection_id, event, rule)
        self.result.data.append((detection_result, self.config.outputs))

    @staticmethod
    def _generate_detection_result(
        pre_detection_id: FieldValue, event: dict, rule: PreDetectorRule
    ) -> dict:
        detection_result = {
            **rule.detection_data,
            "rule_filter": rule.filter_str,
            "description": rule.description,
            "pre_detection_id": pre_detection_id,
        }
        copy_fields_to_event(
            target_event=detection_result,
            source_event=event,
            dotted_field_names=rule.copy_fields_to_detection_event,
            rule=rule,
            skip_missing=True,
        )
        return detection_result
