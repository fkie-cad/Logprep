"""This module contains functionality for pre-detecting attacks."""

from logging import DEBUG, Logger
from uuid import uuid4
from logprep.abc import Processor

from logprep.processor.pre_detector.ip_alerter import IPAlerter
from logprep.processor.pre_detector.rule import PreDetectorRule


class PreDetectorError(BaseException):
    """Base class for PreDetector related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"PreDetector ({name}): {message}")


class PreDetectorConfigurationError(PreDetectorError):
    """Generic PreDetector configuration error."""


class PreDetector(Processor):
    """Processor used to pre_detect log events."""

    detection_results: list

    rule_class = PreDetectorRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        pre_detector_topic = configuration.get("pre_detector_topic")
        alert_ip_list_path = configuration.get("alert_ip_list_path")
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._pre_detector_topic = pre_detector_topic
        self._event = None
        self._ids = []
        self._ip_alerter = IPAlerter(alert_ip_list_path)

    def process(self, event: dict) -> tuple:
        self._event = event
        self.detection_results = []
        super().process(event)
        return (
            (self.detection_results, self._pre_detector_topic) if self.detection_results else None
        )

    def _apply_rules(self, event, rule):
        if not (
            self._ip_alerter.has_ip_fields(rule)
            and not self._ip_alerter.is_in_alerts_list(rule, event)
        ):
            if self._logger.isEnabledFor(DEBUG):
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
