"""
Common
======

Configuration properties shared between input types.

.. autoclass:: logprep.util.preprocessor.PreprocessingConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.preprocessor.FullEventConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.preprocessor.TimeDeltaConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.preprocessor.HmacConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:
"""

from functools import cached_property
from typing import Any, Protocol
from zoneinfo import ZoneInfo


import base64
import hashlib
import json
import os
import zlib
from hmac import HMAC

from msgspec import DecodeError


from logprep.ng.abc.event import LogEvent
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.helper import (
    MISSING,
    FieldValue,
    Missing,
    add_fields_to,
    get_dotted_field_list,
    get_dotted_field_value,
    get_dotted_field_value_with_missing,
)
from logprep.util.preprocessor import (
    FullEventConfig,
    HmacConfig,
    PreprocessingConfig,
    TimeDeltaConfig,
)
from logprep.util.time import UTC, TimeParser, TimeParserException


class PreprocessingError(Exception):
    pass


class Decoder(Protocol):
    def decode(self, data: str) -> Any: ...


class Encoder(Protocol):
    def encode(self, obj: Any) -> bytes: ...


class Preprocessor:

    def __init__(
        self,
        config: PreprocessingConfig,
        version_info: dict[str, FieldValue],
        decoder: Decoder,
        encoder: Encoder,
    ) -> None:
        self._config = config
        self._decoder = decoder
        self._encoder = encoder
        self._version_info = version_info

    @property
    def _add_hmac(self) -> bool:
        """Check and return if a hmac should be added or not."""
        return self._config.hmac.all_set()

    @property
    def _add_version_info(self) -> bool:
        """Check and return if the version info should be added to the event."""
        return bool(self._config.version_info_target_field)

    @cached_property
    def _log_arrival_timestamp_timezone(self) -> ZoneInfo:
        """Returns the timezone for log arrival timestamps"""
        return ZoneInfo("UTC")

    @property
    def _add_log_arrival_time_information(self) -> bool:
        """Check and return if the log arrival time info should be added to the event."""
        return bool(self._config.log_arrival_time_target_field)

    @property
    def _add_log_arrival_timedelta_information(self) -> bool:
        """Check and return if the log arrival timedelta info should be added to the event."""
        log_arrival_timedelta_present = self._add_log_arrival_time_information
        log_arrival_time_target_field_present = bool(self._config.log_arrival_timedelta)
        return log_arrival_time_target_field_present & log_arrival_timedelta_present

    @property
    def _add_env_enrichment(self) -> bool:
        """Check and return if the env enrichment should be added to the event."""
        return bool(self._config.enrich_by_env_variables)

    @property
    def _add_full_event_to_target_field(self) -> bool:
        """Check and return if the event should be written into one singular field."""
        return bool(self._config.add_full_event_to_target_field)

    async def preprocess(self, event: LogEvent) -> None:
        try:
            if self._add_full_event_to_target_field:
                assert self._config.add_full_event_to_target_field is not None
                self._write_full_event_to_target_field(
                    event.data,
                    event.original,
                    self._config.add_full_event_to_target_field,
                )
            if self._add_hmac:
                self._add_hmac_to(event.data, event.original, self._config.hmac)
            if self._add_version_info:
                self._add_version_information_to_event(
                    event.data,
                    self._config.version_info_target_field,
                )
            if self._add_log_arrival_time_information:
                self._add_arrival_time_information_to_event(
                    event.data,
                    self._config.log_arrival_time_target_field,
                )
            if self._add_log_arrival_timedelta_information:
                assert self._config.log_arrival_timedelta is not None
                self._add_arrival_timedelta_information_to_event(
                    event.data,
                    self._config.log_arrival_timedelta,
                    self._config.log_arrival_time_target_field,
                )
            if self._add_env_enrichment:
                self._add_env_enrichment_to_event(event.data, self._config.enrich_by_env_variables)
        except (FieldExistsWarning, TimeParserException, DecodeError, UnicodeDecodeError) as error:
            raise PreprocessingError(str(error)) from error

    def _add_env_enrichment_to_event(self, event: dict, enrichments: dict) -> None:
        """Add the env enrichment information to the event"""
        fields = {
            target: os.environ.get(variable_name, "")
            for target, variable_name in enrichments.items()
        }
        add_fields_to(event, fields)

    def _add_arrival_time_information_to_event(self, event: dict, target: str) -> None:
        time = TimeParser.now(self._log_arrival_timestamp_timezone).isoformat()
        try:
            add_fields_to(event, {target: time})
        except FieldExistsWarning as error:
            if len(get_dotted_field_list(target)) == 1:
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
        raw_event: bytes | None,
        target: FullEventConfig,
    ) -> None:
        if raw_event is None:
            raw_event = self._encoder.encode(event_dict)

        complete_event: str | dict = {}
        if target.format == "dict":
            complete_event = self._decoder.decode(raw_event.decode("utf-8"))
        else:
            complete_event = json.dumps(raw_event.decode("utf-8"))

        if target.clear_event:
            event_dict.clear()
        add_fields_to(
            event_dict, fields={target.target_field: complete_event}, overwrite_target=True
        )

    def _add_arrival_timedelta_information_to_event(
        self,
        event: dict,
        log_arrival_timedelta: TimeDeltaConfig,
        log_arrival_time_target_field: str,
    ) -> None:
        target_field = log_arrival_timedelta.target_field
        reference_target_field = log_arrival_timedelta.reference_field
        time_reference = get_dotted_field_value(event, reference_target_field)
        log_arrival_time = get_dotted_field_value(event, log_arrival_time_target_field)
        if time_reference and isinstance(log_arrival_time, str) and isinstance(time_reference, str):
            delta_time_sec = (
                TimeParser.from_string(log_arrival_time).astimezone(UTC)
                - TimeParser.from_string(time_reference).astimezone(UTC)
            ).total_seconds()
            add_fields_to(event, fields={target_field: delta_time_sec})

    def _add_version_information_to_event(self, event: dict, target_field: str) -> None:
        """Add the version information to the event"""
        # pylint: disable=protected-access
        add_fields_to(event, fields={target_field: self._version_info})
        # pylint: enable=protected-access

    def _add_hmac_to(
        self, event_dict: dict, raw_event: bytes | None, hmac_options: HmacConfig
    ) -> dict:
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
        raw_event: bytes
            The raw event how it is received from the input.
        hmac_options: HmacConfig
            The configuration for generating and storing the hmac in the event.

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
        if raw_event is None:
            raw_event = self._encoder.encode(event_dict)

        received_orig_message: bytes | FieldValue | Missing
        if hmac_options.target == "<RAW_MSG>":
            received_orig_message = raw_event
        else:
            received_orig_message = get_dotted_field_value_with_missing(
                event_dict, hmac_options.target
            )

        if received_orig_message is MISSING:
            raise PreprocessingError(f"Couldn't find the hmac target field '{hmac_options.target}'")
        if not isinstance(received_orig_message, (str, bytes)):
            raise PreprocessingError(
                f"Unable to create hmac for data of type '{type(received_orig_message)}'"
            )
        if isinstance(received_orig_message, str):
            received_orig_message = received_orig_message.encode("utf-8")
        hmac = HMAC(
            key=hmac_options.key.encode(),
            msg=received_orig_message,
            digestmod=hashlib.sha256,
        ).hexdigest()
        compressed = zlib.compress(received_orig_message, level=-1)
        new_field = {
            hmac_options.output_field: {
                "hmac": hmac,
                "compressed_base64": base64.b64encode(compressed).decode(),
            }
        }
        add_fields_to(event_dict, new_field)
        return event_dict
