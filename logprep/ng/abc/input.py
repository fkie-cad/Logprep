"""This module provides the abstract base class for all input endpoints.
New input endpoint types are created by implementing it.
"""

import base64
import hashlib
import json
import logging
import os
import zlib
from abc import abstractmethod
from collections.abc import Iterator
from copy import deepcopy
from functools import cached_property, partial
from hmac import HMAC
from typing import Optional, Self
from zoneinfo import ZoneInfo

from attrs import define, field, validators

from logprep.abc.connector import Connector
from logprep.abc.exceptions import LogprepException
from logprep.metrics.metrics import Metric
from logprep.ng.abc.event import EventBacklog
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.helper import add_fields_to, get_dotted_field_value
from logprep.util.time import UTC, TimeParser, TimeParserException
from logprep.util.validators import dict_structure_validator

logger = logging.getLogger("Input")


class InputError(LogprepException):
    """Base class for Input related exceptions."""

    def __init__(self, input_connector: "Input", message: str) -> None:
        input_connector.metrics.number_of_errors += 1
        super().__init__(f"{self.__class__.__name__} in {input_connector.describe()}: {message}")


class CriticalInputError(InputError):
    """A significant error occurred - log and don't process the event."""

    def __init__(self, input_connector: "Input", message, raw_input):
        super().__init__(
            input_connector, f"{message} -> event was written to error output if configured"
        )
        self.raw_input = deepcopy(raw_input)  # is written to error output
        self.message = message


class CriticalInputParsingError(CriticalInputError):
    """The input couldn't be parsed correctly."""


class FatalInputError(InputError):
    """Must not be catched."""


class InputWarning(LogprepException):
    """May be catched but must be displayed to the user/logged."""

    def __init__(self, input_connector: "Input", message: str) -> None:
        input_connector.metrics.number_of_warnings += 1
        super().__init__(f"{self.__class__.__name__} in {input_connector.describe()}: {message}")


class SourceDisconnectedWarning(InputWarning):
    """Lost (or failed to establish) contact with the source."""


@define(kw_only=True)
class HmacConfig:
    """Hmac Configurations
    The hmac itself will be calculated with python's hashlib.sha256 algorithm and the compression
    is based on the zlib library.
    """

    target: str = field(validator=validators.instance_of(str))
    """Defines a field inside the log message which should be used for the hmac
    calculation. If the target field is not found or does not exists an error message
    is written into the configured output field. If the hmac should be calculated on
    the full incoming raw message instead of a subfield the target option should be set to
    :code:`<RAW_MSG>`."""
    key: str = field(validator=validators.instance_of(str))
    """The secret key that will be used to calculate the hmac."""
    output_field: str = field(validator=validators.instance_of(str))
    """The parent name of the field where the hmac result should be written to in the
    original incoming log message. As subfields the result will have a field called :code:`hmac`,
    containing the calculated hmac, and :code:`compressed_base64`, containing the original message
    that was used to calculate the hmac in compressed and base64 encoded. In case the output
    field exists already in the original message an error is raised."""


@define(kw_only=True)
class TimeDeltaConfig:
    """TimeDelta Configurations
    Works only if the preprocessor log_arrival_time_target_field is set."""

    target_field: str = field(validator=(validators.instance_of(str), lambda _, __, x: bool(x)))
    """Defines the fieldname to which the time difference should be written to."""
    reference_field: str = field(validator=(validators.instance_of(str), lambda _, __, x: bool(x)))
    """Defines a field with a timestamp that should be used for the time difference.
    The calculation will be the arrival time minus the time of this reference field."""


@define(kw_only=True)
class FullEventConfig:
    """Full Event Configurations
    Works only if the preprocessor :code:`add_full_event_to_target_field` is set."""

    format: str = field(validator=validators.in_(["dict", "str"]), default="str")
    """Defines the Format in which the event should be written to the new field.
    The default ist :code:`str`, which results in escaped json string"""
    target_field: str = field(validator=validators.instance_of(str), default="event.original")
    """Defines the fieldname which the event should be written to"""
    clear_event: bool = field(validator=validators.instance_of(bool), default=True)
    """Defines if raw event should be the only field."""


class InputIterator(Iterator):
    """Base Class for an input Iterator"""

    def __init__(self, input_connector: "Input", timeout: float):
        """Initialize the input iterator with a timeout.

        Parameters
        ----------
        input_connector : Input
            The input connector to retrieve events from.
        timeout : float
            The time in seconds to wait for the next event before timing out.
        """

        self.input_connector = input_connector
        self.timeout = timeout

    def __iter__(self) -> Self:
        """Return the iterator instance itself.

        Returns
        -------
        Self
            The iterator instance (self).
        """

        return self

    def __next__(self) -> LogEvent | None:
        """Return the next event in the Input Connector within the configured timeout.

        Returns
        -------
        LogEvent | None
            The next event retrieved from the underlying data source.
        """
        event = self.input_connector.get_next(timeout=self.timeout)
        logger.debug(
            "InputIterator fetching next event with timeout %s, is None: %s",
            self.timeout,
            event is None,
        )
        return event


class Input(Connector):
    """Connect to a source for log data."""

    class Metrics(Connector.Metrics):
        """Input Metrics"""

    @define(kw_only=True, slots=False)
    class Config(Connector.Config):
        """Input Configurations"""

        preprocessing: dict = field(
            validator=[
                validators.instance_of(dict),
                partial(
                    dict_structure_validator,
                    reference_dict={
                        "version_info_target_field": Optional[str],
                        "hmac": Optional[HmacConfig],
                        "log_arrival_time_target_field": Optional[str],
                        "log_arrival_timedelta": Optional[TimeDeltaConfig],
                        "enrich_by_env_variables": Optional[dict],
                        "add_full_event_to_target_field": Optional[FullEventConfig],
                    },
                ),
            ],
            default={
                "version_info_target_field": "",
                "hmac": {"target": "", "key": "", "output_field": ""},
                "log_arrival_time_target_field": "",
            },
        )
        """
        All input connectors support different preprocessing methods:

        - `log_arrival_time_target_field` - It is possible to automatically add the arrival time in
          Logprep to every incoming log message. To enable adding arrival times to each event the
          keyword :code:`log_arrival_time_target_field` has to be set under the field
          :code:`preprocessing`. It defines the name of the dotted field in which the arrival
          times should be stored. If the field :code:`preprocessing` and
          :code:`log_arrival_time_target_field` are not present, no arrival timestamp is added
          to the event.
        - `log_arrival_timedelta` - It is possible to automatically calculate the difference
          between the arrival time of logs in Logprep and their generation timestamp, which is then
          added to every incoming log message. To enable adding delta times to each event, the
          keyword :code:`log_arrival_time_target_field` has to be set as a precondition (see
          above). Furthermore, two configurations for the timedelta are needed. A
          :code:`target_field` as well as a :code:`reference_field` has to be set.

            - `target_field` - Defines the fieldname to which the time difference should be
              written to.
            - `reference_field` - Defines a field with a timestamp that should be used for the time
              difference. The calculation will be the arrival time minus the time of this
              reference field.

        - `version_info_target_field` - If required it is possible to automatically add the logprep
          version and the used configuration version to every incoming log message. This helps to
          keep track of the processing of the events when the configuration is changing often. To
          enable adding the versions to each event the keyword :code:`version_info_target_field`
          has to be set under the field :code:`preprocessing`. It defines the name of the parent
          field under which the version info should be given. If the field :code:`preprocessing`
          and :code:`version_info_target_field` are not present then no version information is
          added to the event.
        - `hmac` - If required it is possible to automatically attach an HMAC to incoming log
          messages. To activate this preprocessor the following options should be appended to the
          preprocessor options. This field is completely optional and can also be omitted if no
          hmac is needed.

            - `target` - Defines a field inside the log message which should be used for the hmac
              calculation. If the target field is not found or does not exists an error message
              is written into the configured output field. If the hmac should be calculated on
              the full incoming raw message instead of a subfield the target option should be set to
              :code:`<RAW_MSG>`.
            - `key` - The secret key that will be used to calculate the hmac.
            - `output_field` - The parent name of the field where the hmac result should be written
              to in the original incoming log message. As subfields the result will have a field
              called :code:`hmac`, containing the calculated hmac, and :code:`compressed_base64`,
              containing the original message that was used to calculate the hmac in compressed and
              base64 encoded. In case the output field exists already in the original message an
              error is raised.

        - `enrich_by_env_variables` - If required it is possible to automatically enrich incoming
          events by environment variables. To activate this preprocessor the fields value has to be
          a mapping from the target field name (key) to the environment variable name (value).
        - `add_full_event_to_target_field` - If required it is possible to automatically copy
          all event fields to one singular field or subfield. If needed as an escaped string.
          The exact fields in the event do not have to be known to use this preprocessor. To use this
          preprocessor the fields :code:`format` and :code:`target_field` have to bet set. When the
          format :code:`str` ist set the event is automatically escaped. This can be used to identify
          and resolve mapping errors thrown by opensearch.

            - :code:`format` - specifies the format which the event is written in. The default
              format ist :code:`str` which leads to automatic json escaping of the given event. Also
              possible is the value :code:`dict` which copies the event as mapping to the specified
              :code:`target_field`. If the format :code:`str` is set it is necessary to have a
              timestamp set in the event for opensearch to receive the event in the string format.
              This can be achieved by using the :code:`log_arrival_time_target_field` preprocessor.
            - :code:`target_field` - specifies the field to which the event should be written to.
              the default is :code:`event.original`
            - :code:`clear_event` - specifies if the singular field should be the only field or appended.
              the default is :code: `True`
        """

        _version_information: dict = field(
            validator=validators.instance_of(dict),
            default={
                "logprep": "",
                "configuration": "",
            },
        )

    def __init__(self, name: str, configuration: "Input.Config") -> None:
        self.event_backlog: EventBacklog = SetEventBacklog()
        super().__init__(name, configuration)

    def __call__(self, *, timeout: float) -> InputIterator:
        """Create and return a new input iterator with the specified timeout.

        This enables the input connector instance to be called directly as a function
        to obtain an iterator, e.g. `for event in input_connector(timeout=5.0):`.

        Parameters
        ----------
        timeout : float
            Keyword-only. The time to wait for blocking.

        Returns
        -------
        InputIterator
            An iterator object that retrieves events from the input connector.

        Examples
        --------
        >>> input_connector = Input(...)
        >>> for event in input_connector(timeout=5.0):
        ...     process(event)
        """

        return InputIterator(self, timeout)

    def acknowledge(self) -> None:
        """Acknowledge all delivered events, so Input Connector can return final ACK state.

        As side effect, all older events with state ACKED has to be removed from `event_backlog`
        before acknowledging new ones.
        """

        self.event_backlog.unregister(state_type=EventStateType.ACKED)

        for event in self.event_backlog.get(state_type=EventStateType.DELIVERED):
            event.state.next_state()

    @property
    def _add_hmac(self) -> bool:
        """Check and return if a hmac should be added or not."""
        hmac_options = self._config.preprocessing.get("hmac")
        if not hmac_options:
            return False
        return all(bool(hmac_options[option_key]) for option_key in hmac_options)

    @property
    def _add_version_info(self) -> bool:
        """Check and return if the version info should be added to the event."""
        return bool(self._config.preprocessing.get("version_info_target_field"))

    @cached_property
    def _log_arrival_timestamp_timezone(self) -> ZoneInfo:
        """Returns the timezone for log arrival timestamps"""
        return ZoneInfo("UTC")

    @property
    def _add_log_arrival_time_information(self) -> bool:
        """Check and return if the log arrival time info should be added to the event."""
        return bool(self._config.preprocessing.get("log_arrival_time_target_field"))

    @property
    def _add_log_arrival_timedelta_information(self) -> bool:
        """Check and return if the log arrival timedelta info should be added to the event."""
        log_arrival_timedelta_present = self._add_log_arrival_time_information
        log_arrival_time_target_field_present = bool(
            self._config.preprocessing.get("log_arrival_timedelta")
        )
        return log_arrival_time_target_field_present & log_arrival_timedelta_present

    @property
    def metric_labels(self) -> dict:
        """Return the metric labels for this component."""
        return {
            "component": "input",
            "description": self.describe(),
            "type": self._config.type,
            "name": self.name,
        }

    @property
    def _add_env_enrichment(self) -> bool:
        """Check and return if the env enrichment should be added to the event."""
        return bool(self._config.preprocessing.get("enrich_by_env_variables"))

    @property
    def _add_full_event_to_target_field(self) -> bool:
        """Check and return if the event should be written into one singular field."""
        return bool(self._config.preprocessing.get("add_full_event_to_target_field"))

    def _get_raw_event(self, timeout: float) -> bytes | None:  # pylint: disable=unused-argument
        """Implements the details how to get the raw event

        Parameters
        ----------
        timeout : float
            timeout

        Returns
        -------
        raw_event : bytearray
            The retrieved raw event
        """
        return None

    @abstractmethod
    def _get_event(self, timeout: float) -> tuple:
        """Implements the details how to get the event

        Parameters
        ----------
        timeout : float
            timeout

        Returns
        -------
        (event, raw_event, metadata)
        """

    def _register_failed_event(
        self,
        event: dict | None,
        raw_event: bytes | None,
        metadata: dict | None,
        error: Exception,
    ) -> None:
        """Helper method to register the failed event to event backlog."""

        error_log_event = LogEvent(
            data=event if isinstance(event, dict) else {},
            original=raw_event if raw_event is not None else b"",
            metadata=metadata,
        )
        error_log_event.errors.append(error)
        error_log_event.state.current_state = EventStateType.FAILED

        self.event_backlog.register(events=[error_log_event])

    @Metric.measure_time()
    def get_next(self, timeout: float) -> LogEvent | None:
        """Return the next document

        Parameters
        ----------
        timeout : float
           The time to wait for blocking.

        Returns
        -------
        input : LogEvent, None
            Input log data.
        """
        self.acknowledge()
        event: dict | None = None
        raw_event: bytearray | None = None
        metadata: dict | None = None

        try:
            event, raw_event, metadata = self._get_event(timeout)

            if event is None:
                return None

            if not isinstance(event, dict):
                raise CriticalInputError(self, "not a dict", event)

            self.metrics.number_of_processed_events += 1

            try:
                if self._add_full_event_to_target_field:
                    self._write_full_event_to_target_field(event, raw_event)
                if self._add_hmac:
                    event = self._add_hmac_to(event, raw_event)
                if self._add_version_info:
                    self._add_version_information_to_event(event)
                if self._add_log_arrival_time_information:
                    self._add_arrival_time_information_to_event(event)
                if self._add_log_arrival_timedelta_information:
                    self._add_arrival_timedelta_information_to_event(event)
                if self._add_env_enrichment:
                    self._add_env_enrichment_to_event(event)
            except (FieldExistsWarning, TimeParserException) as error:
                raise CriticalInputError(self, error.args[0], event) from error
        except CriticalInputError as error:
            self._register_failed_event(
                event=event,
                raw_event=raw_event,
                metadata=metadata,
                error=error,
            )
            return None

        log_event = LogEvent(
            data=event,
            original=raw_event,
            metadata=metadata,
        )

        self.event_backlog.register(events=[log_event])
        log_event.state.next_state()

        return log_event

    def batch_finished_callback(self) -> None:
        """Can be called by output connectors after processing a batch of one or more records."""

    def _add_env_enrichment_to_event(self, event: dict) -> None:
        """Add the env enrichment information to the event"""
        enrichments = self._config.preprocessing.get("enrich_by_env_variables")
        if not enrichments:
            return
        fields = {
            target: os.environ.get(variable_name, "")
            for target, variable_name in enrichments.items()
        }
        add_fields_to(event, fields)

    def _add_arrival_time_information_to_event(self, event: dict) -> None:
        target = self._config.preprocessing.get("log_arrival_time_target_field")
        time = TimeParser.now(self._log_arrival_timestamp_timezone).isoformat()
        try:
            add_fields_to(event, {target: time})
        except FieldExistsWarning as error:
            if len(target.split(".")) == 1:
                raise error
            original_target = target
            target_value = get_dotted_field_value(event, target)
            while target_value is None:
                target, _, _ = target.rpartition(".")
                target_value = get_dotted_field_value(event, target)
            add_fields_to(event, {original_target: time}, overwrite_target=True)
            add_fields_to(event, {f"{target}.@original": target_value})
            assert True

    def _write_full_event_to_target_field(
        self,
        event_dict: dict,
        raw_event: bytearray | None,
    ) -> None:
        target = self._config.preprocessing.get("add_full_event_to_target_field")
        complete_event = {}
        if raw_event is None:
            raw_event = self._encoder.encode(event_dict)
        if target["format"] == "dict":
            complete_event = self._decoder.decode(raw_event.decode("utf-8"))
        else:
            complete_event = json.dumps(raw_event.decode("utf-8"))
        clear_event = target.get("clear_event", True)
        if clear_event:
            event_dict.clear()
        add_fields_to(
            event_dict, fields={target["target_field"]: complete_event}, overwrite_target=True
        )

    def _add_arrival_timedelta_information_to_event(self, event: dict) -> None:
        log_arrival_timedelta_config = self._config.preprocessing.get("log_arrival_timedelta")
        log_arrival_time_target_field = self._config.preprocessing.get(
            "log_arrival_time_target_field"
        )
        target_field = log_arrival_timedelta_config.get("target_field")
        reference_target_field = log_arrival_timedelta_config.get("reference_field")
        time_reference = get_dotted_field_value(event, reference_target_field)
        log_arrival_time = get_dotted_field_value(event, log_arrival_time_target_field)
        if time_reference:
            delta_time_sec = (
                TimeParser.from_string(log_arrival_time).astimezone(UTC)
                - TimeParser.from_string(time_reference).astimezone(UTC)
            ).total_seconds()
            add_fields_to(event, fields={target_field: delta_time_sec})

    def _add_version_information_to_event(self, event: dict) -> None:
        """Add the version information to the event"""
        target_field = self._config.preprocessing.get("version_info_target_field")
        # pylint: disable=protected-access
        add_fields_to(event, fields={target_field: self._config._version_information})
        # pylint: enable=protected-access

    def _add_hmac_to(self, event_dict: dict, raw_event: bytearray | None) -> dict:
        """
        Calculates an HMAC (Hash-based message authentication code) based on a given target field
        and adds it to the given event. If the target field has the value '<RAW_MSG>' the full raw
        byte message is used instead as a target for the HMAC calculation. If no raw_event was given
        the HMAC is calculated on the parsed event_dict as a fallback. As a result this preprocessor
        the target field value and the resulting hmac will be added to the original event. The
        target field value will be compressed and base64 encoded to reduce memory usage.

        Parameters
        ----------
        event_dict: dict
            The event to which the calculated hmac should be appended
        raw_event: bytearray, None
            The raw event how it is received from the input.

        Returns
        -------
        event_dict: dict
            The original event extended with a field that has the hmac and the corresponding target
            field, which was used to calculate the hmac.

        Raises
        ------
        CriticalInputError
            If the hmac could not be added to the event because the desired output field already
            exists or can't be found.
        """
        hmac_options = self._config.preprocessing.get("hmac", {})
        hmac_target_field_name = hmac_options.get("target")

        if raw_event is None:
            raw_event = self._encoder.encode(event_dict)

        if hmac_target_field_name == "<RAW_MSG>":
            received_orig_message = raw_event
        else:
            received_orig_message = get_dotted_field_value(event_dict, hmac_target_field_name)

        if received_orig_message is None:
            error_message = f"Couldn't find the hmac target field '{hmac_target_field_name}'"
            raise CriticalInputError(self, error_message, raw_event)
        if isinstance(received_orig_message, str):
            received_orig_message = received_orig_message.encode("utf-8")
        hmac = HMAC(
            key=hmac_options.get("key").encode(),
            msg=received_orig_message,
            digestmod=hashlib.sha256,
        ).hexdigest()
        compressed = zlib.compress(received_orig_message, level=-1)
        new_field = {
            hmac_options.get("output_field"): {
                "hmac": hmac,
                "compressed_base64": base64.b64encode(compressed).decode(),
            }
        }
        add_fields_to(event_dict, new_field)
        return event_dict
