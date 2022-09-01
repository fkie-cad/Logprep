"""This module provides the abstract base class for all input endpoints.

New input endpoint types are created by implementing it.

"""

import base64
import hashlib
from typing import Dict, Tuple
import zlib
from abc import abstractmethod
from hmac import HMAC

from attrs import define, field, validators
from logprep.util.helper import add_field_to, get_dotted_field_value

from .connector import Connector


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


class Input(Connector):
    """Connect to a source for log data."""

    @define(kw_only=True, slots=False)
    class Config(Connector.Config):
        """Input Configurations"""

        preprocessing: dict = field(
            validator=validators.instance_of(dict),
            default={
                "version_info_target_field": "",
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
        )

    _output: Connector

    __slots__ = ["_output"]

    @property
    def _add_hmac(self):
        return all(bool(hmac_value) for hmac_value in self._config.preprocessing.get("hmac"))

    def setup(self):
        """Set the input up, e.g. connect to a database.

        This is optional.

        """

    def _get_raw_event(self, timeout: float) -> bytearray:
        """Implements the details how to get the event

        Parameters
        ----------
        timeout : float
            timeout
        """
        return None

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
        return None, self._get_raw_event(timeout)

    def get_next(self, timeout: float) -> dict:
        """Return the next document, blocking if none is available.

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
        if self._add_hmac:
            event = self._add_hmac_to(event, raw_event)
        return event

    def batch_finished_callback(self):
        """Can be called by output connectors after processing a batch of one or more records."""

    def shut_down(self):
        """Close the input down, e.g. close all connections.

        This is optional.

        """

    def _add_hmac_to(self, event_dict, raw_event):
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
        hmac_target_field_name: str
            The dotted field name of the target value that should be used for the hmac calculation.
            If instead '<RAW_MSG>' is used then the hmac will be calculated over the full raw event.
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

        if hmac_target_field_name == "<RAW_MSG>":
            received_orig_message = raw_event
        else:
            received_orig_message = get_dotted_field_value(event_dict, hmac_target_field_name)

        if received_orig_message is None:
            hmac = "error"
            received_orig_message = (
                f"<expected hmac target field '{hmac_target_field_name}' not found>".encode()
            )
            self._output.store_failed(
                f"Couldn't find the hmac target field '{hmac_target_field_name}'",
                event_dict,
                event_dict,
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
            self._output.store_failed(
                f"Couldn't add the hmac to the input event as the desired output "
                f"field '{hmac_options.get('output_field')}' already exist.",
                event_dict,
                event_dict,
            )
        return event_dict
