"""
PreDetector
-----------

The `pre_detector` is a processor that creates alerts for matching events. It adds MITRE ATT&CK
data to the alerts.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - predetectorname:
        type: pre_detector
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        pre_detector_topic: sre_topic
        alert_ip_list_path: /tmp/ip_list.yml
"""
import sys
from logging import DEBUG, Logger
from uuid import uuid4

from attr import define, field, validators
from logprep.abc import Processor
from logprep.processor.pre_detector.ip_alerter import IPAlerter
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.util.validators import file_validator

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class PreDetectorError(BaseException):
    """Base class for PreDetector related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"PreDetector ({name}): {message}")


class PreDetectorConfigurationError(PreDetectorError):
    """Generic PreDetector configuration error."""


class PreDetector(Processor):
    """Processor used to pre_detect log events."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """PreDetector config"""

        pre_detector_topic: str = field(validator=validators.instance_of(str))
        """
        A Kafka topic for the detection results of the Predetector.
        Results in this topic can be linked to the original event via a `pre_detector_id`.
        """
        alert_ip_list_path: str = field(default=None, validator=file_validator)
        """
        Path to a YML file or a list of paths to YML files with dictionaries of IPs.
        It is used by the Predetector to throw alerts if one of the IPs is found
        in fields that were defined in a rule.

        It uses IPs or networks in the CIDR format as keys and can contain expiration
        dates in the ISO format as values.
        If a value is empty, then there is no expiration date for the IP check.
        If a checked IP is covered by an IP and a network in the dictionary
        (i.e. IP 127.0.0.1 and network 127.0.0.0/24 when checking 127.0.0.1),
        then the expiration date of the IP is being used.
        """

    __slots__ = ["detection_results", "_pre_detector_topic", "_ids"]

    _ids: list

    detection_results: list

    rule_class = PreDetectorRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._ids = []

    @cached_property
    def _ip_alerter(self):
        return IPAlerter(self._config.alert_ip_list_path)

    def process(self, event: dict) -> tuple:
        self._event = event
        self.detection_results = []
        super().process(event)
        return (
            (self.detection_results, self._config.pre_detector_topic)
            if self.detection_results
            else None
        )

    def _apply_rules(self, event, rule):
        if not (
            self._ip_alerter.has_ip_fields(rule)
            and not self._ip_alerter.is_in_alerts_list(rule, event)
        ):
            if self._logger.isEnabledFor(DEBUG):  # pragma: no cover
                self._logger.debug(f"{self.describe()} processing matching event")
            self._get_detection_result(rule, self.detection_results)
        if "@timestamp" in event:
            for detection in self.detection_results:
                detection["@timestamp"] = event["@timestamp"]

    def _get_detection_result(self, rule: PreDetectorRule, detection_results: list):
        if self._event.get("pre_detection_id") is None:
            self._event["pre_detection_id"] = str(uuid4())

        detection_results.append(self._generate_detection_result(rule))

    def _generate_detection_result(self, rule: PreDetectorRule):
        detection_result = rule.detection_data
        detection_result["rule_filter"] = rule.filter_str
        detection_result["description"] = rule.description
        detection_result["pre_detection_id"] = self._event["pre_detection_id"]
        if "host" in self._event and "name" in self._event["host"]:
            detection_result["host"] = {"name": self._event["host"]["name"]}

        return detection_result
