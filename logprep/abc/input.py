"""This module provides the abstract base class for all input endpoints.
New input endpoint types are created by implementing it.
"""

import base64
import hashlib
import zlib
from abc import abstractmethod
from functools import partial
from hmac import HMAC
from typing import Tuple, Optional

from attrs import define, field, validators

from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.time_measurement import TimeMeasurement
from logprep.abc import Connector
from logprep.util.validators import dict_structure_validator


class InputError(BaseException):
    """Base class for Input related exceptions."""


class CriticalInputError(InputError):
    """A significant error occurred - log and don't process the event."""

    def __init__(self, message, raw_input):
        self.raw_input = raw_input
        super().__init__(message)


class FatalInputError(InputError):
    """Must not be catched."""


class WarningInputError(InputError):
    """May be catched but must be displayed to the user/logged."""


class SourceDisconnectedError(WarningInputError):
    """Lost (or failed to establish) contact with the source."""


class InfoInputError(InputError):
    """Informational exceptions, e.g. to inform that a timeout occurred"""


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


class Input(Connector):
    """Connect to a source for log data."""

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
                    },
                ),
            ],
            default={
                "version_info_target_field": "",
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
        )
        """
        All input connectors support different preprocessing methods:

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
        """

        _version_information: dict = field(
            validator=validators.instance_of(dict),
            default={
                "logprep": "",
                "configuration": "",
            },
        )

    __slots__ = []

    @property
    def _add_hmac(self):
        """Check and return if a hmac should be added or not."""
        hmac_options = self._config.preprocessing.get("hmac")
        if not hmac_options:
            return False
        return all(bool(hmac_options[option_key]) for option_key in hmac_options)

    @property
    def _add_version_info(self):
        """Check and return if the version info should be added to the event."""
        return bool(self._config.preprocessing.get("version_info_target_field"))

    def _get_raw_event(self, timeout: float) -> bytearray:
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
    def _get_event(self, timeout: float) -> Tuple:
        """Implements the details how to get the event

        Parameters
        ----------
        timeout : float
            timeout

        Returns
        -------
        (event, raw_event)
        """

    @TimeMeasurement.measure_time()
    def get_next(self, timeout: float) -> Tuple[dict, str]:
        """Return the next document

        Parameters
        ----------
        timeout : float
           The time to wait for blocking.

        Returns
        -------
        input : dict
            Input log data.

        Raises
        ------
        TimeoutWhileWaitingForInputError
            After timeout (usually a fraction of seconds) if no input data was available by then.
        """
        event, raw_event = self._get_event(timeout)
        non_critical_error_msg = None
        if event is not None and not isinstance(event, dict):
            raise CriticalInputError("not a dict", event)
        if event and self._add_hmac:
            event, non_critical_error_msg = self._add_hmac_to(event, raw_event)
        if event and self._add_version_info:
            self._add_version_information_to_event(event)
        self.metrics.number_of_processed_events += 1
        return event, non_critical_error_msg

    def batch_finished_callback(self):
        """Can be called by output connectors after processing a batch of one or more records."""

    def _add_version_information_to_event(self, event: dict):
        """Add the version information to the event"""
        target_field = self._config.preprocessing.get("version_info_target_field")
        add_field_to(event, target_field, self._config._version_information)

    def _add_hmac_to(self, event_dict, raw_event) -> Tuple[dict, str]:
        """
        Calculates an HMAC (Hash-based message authentication code) based on a given target field
        and adds it to the given event. If the target field has the value '<RAW_MSG>' the full raw
        byte message is used instead as a target for the HMAC calculation. As a result the target
        field value and the resulting hmac will be added to the original event. The target field
        value will be compressed and base64 encoded though to reduce memory usage.

        Parameters
        ----------
        event_dict: dict
            The event to which the calculated hmac should be appended
        raw_event: bytearray
            The raw event how it is received from kafka.

        Returns
        -------
        event_dict: dict
            The original event extended with a field that has the hmac and the corresponding target
            field, which was used to calculate the hmac.
        """
        hmac_options = self._config.preprocessing.get("hmac", {})
        hmac_target_field_name = hmac_options.get("target")
        non_critical_error_msg = None

        if hmac_target_field_name == "<RAW_MSG>":
            received_orig_message = raw_event
        else:
            received_orig_message = get_dotted_field_value(event_dict, hmac_target_field_name)

        if received_orig_message is None:
            hmac = "error"
            received_orig_message = (
                f"<expected hmac target field '{hmac_target_field_name}' not found>".encode()
            )
            non_critical_error_msg = (
                f"Couldn't find the hmac target " f"field '{hmac_target_field_name}'"
            )
        else:
            if isinstance(received_orig_message, str):
                received_orig_message = received_orig_message.encode("utf-8")
            hmac = HMAC(
                key=hmac_options.get("key").encode(),
                msg=received_orig_message,
                digestmod=hashlib.sha256,
            ).hexdigest()
        compressed = zlib.compress(received_orig_message, level=-1)
        hmac_output = {"hmac": hmac, "compressed_base64": base64.b64encode(compressed).decode()}
        add_was_successful = add_field_to(
            event_dict,
            hmac_options.get("output_field"),
            hmac_output,
        )
        if not add_was_successful:
            non_critical_error_msg = (
                f"Couldn't add the hmac to the input event as the desired "
                f"output field '{hmac_options.get('output_field')}' already "
                f"exist."
            )
        return event_dict, non_critical_error_msg
