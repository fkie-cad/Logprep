# pylint: disable=too-few-public-methods

"""abstract module for event"""

from collections.abc import Sequence
import json
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
import typing

from attrs import define, field, validators

from logprep.abc.exceptions import LogprepExceptionGroup
from logprep.util.helper import FieldValue


@define
class EventMetadata:
    """EventMetadata Class to define the Interface"""


class _FailableEvent(Protocol):
    def mark_failed(self, error: Exception) -> None:
        """Register an event-related error and hence mark the event as failed"""

    def is_failed(self) -> bool:
        """Checks if an error has been registered with this event"""


@runtime_checkable
class AcknowledgableEvent(_FailableEvent, Protocol):
    """
    Protocol encapsulating the aspects of an event which has been
    received from an `Input` and might therefore be acknowledgedable.
    """

    metadata: EventMetadata


@runtime_checkable
class OutputEvent(_FailableEvent, Protocol):
    """Protocol encapsulating the aspects of an event which can be
    handed to an `Output` for sending."""

    data: dict[str, FieldValue]

    output_target: str | None
    """Indicates to which target inside an output the event should be routed"""

    stored: bool


@runtime_checkable
class ProcessableEvent(_FailableEvent, Protocol):
    """Protocol encapsulating the aspects of an event which can be
    handed to an `Output` for sending."""

    data: dict[str, FieldValue]
    output_target: str | None
    """Indicates to which target inside an output the event should be routed"""


@define
class _BaseFailableEvent(_FailableEvent):
    """
    Base class for events which can fail during processing.
    """

    # TODO change to single item?
    _errors: list[Exception] = field(factory=list, init=False)

    warnings: list[Exception] = field(factory=list, init=False, eq=False)
    """
    Warnings occurred during processing. Deprecated.
    """

    def mark_failed(self, error: Exception) -> None:
        self._errors.append(error)

    def is_failed(self) -> bool:
        return bool(self._errors) or bool(self.warnings)

    @property
    def errors(self) -> Sequence[Exception]:
        """
        Returns all registered errors, empty list if there are none.
        Caution: Might be changed to a single-valued attribute in the future.
        """
        return self._errors


# TODO move somewhere else
@define
class OutputSpec:
    """
    Specifies an output by name and which target (e.g. topic for kafka, index for opensearch)
    should be addressed.
    """

    output_name: str = field(validator=(validators.instance_of(str), validators.min_len(1)))
    output_target: str = field(validator=(validators.instance_of(str), validators.min_len(1)))


@define
class ExtraDataEvent(_BaseFailableEvent, OutputEvent):
    """
    Abstract base class for events that can contain extra data.
    """

    data: dict[str, FieldValue] = field()

    output_name: str | None = field(kw_only=True)
    output_target: str | None = field(kw_only=True)

    stored: bool = field(kw_only=True, default=False)


@define
class LogEvent(_BaseFailableEvent, OutputEvent, ProcessableEvent):
    """The primary log event entity"""

    data: dict[str, FieldValue] = field()

    original: bytes | None = field(kw_only=True)
    metadata: EventMetadata = field(kw_only=True)

    output_name: str | None = field(kw_only=True, default=None)
    output_target: str | None = field(kw_only=True, default=None)

    extra_data: list[ExtraDataEvent] = field(kw_only=True, factory=list)

    stored: bool = field(kw_only=True, default=False)


@define
class ErrorEvent(_BaseFailableEvent, OutputEvent):
    """
    ErrorEvent represents a failed event.
    """

    data: dict[str, FieldValue] = field()

    metadata: EventMetadata | None = field(kw_only=True, default=None)

    stored: bool = field(kw_only=True, default=False)

    output_target: None = field(kw_only=True, init=False, default=None)
    """Use the default target of the `Output` component"""

    @property
    def reason(self) -> str:
        return typing.cast(str, self.data["reason"])

    @classmethod
    def from_failed_event(cls, event: LogEvent) -> "ErrorEvent":
        reason = (
            LogprepExceptionGroup("Error during processing", event.errors)
            if event.errors
            else Exception("Unknown error")
        )
        return cls(
            data={
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": str(reason),
                # TODO shouldnt we send the raw bytes? at least we should handle decoding failures properly
                "original": (
                    event.original.decode("utf-8", errors="ignore")
                    if event.original is not None
                    else None
                ),
                "event": json.dumps(event.data),
            },
            metadata=event.metadata,
        )

    @classmethod
    def from_input_failure(
        cls, cause: str | Exception, original: bytes | None, metadata: EventMetadata | None
    ) -> "ErrorEvent":
        return cls(
            data={
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": str(cause) if isinstance(cause, Exception) else cause,
                "original": (
                    original.decode("utf-8", errors="ignore") if original is not None else None
                ),
                # "event": json.dumps(event.data),
            },
            metadata=metadata,
        )
