# pylint: disable=too-few-public-methods

"""abstract module for event"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterable, Optional, Union

from logprep.ng.event.event_state import EventState, EventStateType
from logprep.util.helper import (
    add_fields_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)

if TYPE_CHECKING:  # pragma: no cover
    from logprep.processor.base.rule import Rule


class EventMetadata(ABC):
    """Abstract EventMetadata Class to define the Interface"""


class Event(ABC):
    """
    Abstract base class representing an event in the processing pipeline.

    Encapsulates data, warnings, errors, and processing state.
    """

    __slots__: tuple[str, ...] = ("data", "_state", "errors", "warnings")

    def __init__(
        self,
        data: dict[str, Any],
        *,
        state: EventState | None = None,
    ) -> None:
        """
        Initialize an Event instance.

        Parameters
        ----------
        data : dict[str, Any]
            The raw or processed data associated with the event.
        state : EventState, optional
            An optional initial EventState. Defaults to a new EventState() if not provided.

        Examples
        --------
        Basic usage with automatic state:

        >>> event = Event({"source": "syslog"})
        >>> event.data
        {'source': 'syslog'}
        >>> event.state.current_state.name
        'RECEIVING'

        Providing a custom state:

        >>> custom_state = EventState()
        >>> event = Event({"source": "api"}, state=custom_state)
        >>> event.state is custom_state
        True

        Handling warnings and errors:

        >>> event = Event({"id": 123})
        >>> event.warnings.append("Missing timestamp")
        >>> event.errors.append(ValueError("Invalid format"))
        >>> event.warnings
        ['Missing timestamp']
        >>> isinstance(event.errors[0], ValueError)
        True
        """

        self._state: EventState = EventState() if state is None else state
        self.data: dict[str, Any] = data
        self.warnings: list[str] = []
        self.errors: list[Exception] = []
        super().__init__()

    def __eq__(self, other: object) -> bool:
        """
        Determines whether two Event instances are considered equal.
        Equality is defined by the equality of their `data` content.

        Parameters
        ----------
        other : object
            The object to compare against.

        Returns
        -------
        bool
            True if the other object is an Event and its `data` is equal to this instance's `data`.
        """

        if not isinstance(other, Event):
            return NotImplemented

        return self.data == other.data

    def __hash__(self) -> int:
        """
        Returns a hash based on the immutable representation of the `data` field.
        This enables Event instances to be used as keys in dictionaries or as members of sets.

        Returns
        -------
        int
            A hash value derived from the event's `data`.
        """

        return hash(self._deep_freeze(self.data))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(data={self.data}, state={self.state.current_state})"

    @property
    def state(self) -> EventState:
        """Return the current EventState instance."""

        return self._state

    def _deep_freeze(self, obj: Any) -> Any:
        """
        Recursively converts a data structure into a
        hashable (immutable) representation. Used internally for generating
        consistent hash values from nested dictionaries/lists.

        Parameters
        ----------
        obj : Any
            The object (usually dict or list) to be frozen.

        Returns
        -------
        Any
            A hashable, immutable version of the input object.
        """

        if isinstance(obj, dict):
            return frozenset((k, self._deep_freeze(v)) for k, v in obj.items())

        if isinstance(obj, list):
            return tuple(self._deep_freeze(x) for x in obj)

        if isinstance(obj, set):
            return frozenset(self._deep_freeze(x) for x in obj)

        return obj

    def add_fields_to(
        self,
        fields: dict[str, Any],
        rule: "Rule" = None,
        merge_with_target: bool = False,
        overwrite_target: bool = False,
    ) -> None:
        """
        Add one or more fields to the target dictionary.

        This method wraps the global `add_fields_to` utility function from
        `logprep.util.helper`, allowing convenient field injection, merging,
        and optional overwriting.

        Args:
            fields (dict): A dictionary of fields to add.
            rule (Rule, optional): The rule context under which fields are added.
            merge_with_target (bool): Whether to merge dictionaries recursively instead
                of overwriting.
            overwrite_target (bool): Whether to overwrite existing values in the target.

        Returns:
            None
        """
        return add_fields_to(self.data, fields, rule, merge_with_target, overwrite_target)

    def get_dotted_field_value(self, dotted_field: str) -> Any:
        """
        Shortcut method that delegates to the global `get_dotted_field_value` helper.

        Parameters
        ----------
        dotted_field : str
            The dotted path of the field to retrieve.

        Returns
        -------
        Any
            The value at the specified dotted path, or None if not found.
        """
        return get_dotted_field_value(self.data, dotted_field)

    def pop_dotted_field_value(self, dotted_field: str) -> Optional[Union[dict, list, str]]:
        """
        Shortcut method that delegates to the global `pop_dotted_field_value` helper.

        Parameters
        ----------
        dotted_field : str
            The dotted path of the field to remove.

        Returns
        -------
        Any
            The removed value, or None if the path did not exist.
        """
        return pop_dotted_field_value(self.data, dotted_field)


class ExtraDataEvent(Event):
    """
    Abstract base class for events that can contain extra data.

    This class extends the basic Event functionality to include a list of
    additional Event instances that are related to this event.
    """

    __slots__ = ("outputs",)

    outputs: tuple[dict[str, str]]

    def __init__(
        self, data: dict[str, str], *, outputs: tuple[dict], state: EventState | None = None
    ) -> None:
        """
        Parameters
        ----------
        data : dict[str, str]
            The main data payload for the SRE event.
        state : EventState
            The state of the SRE event.
        outputs : Iterable[str]
            The collection of output connector names associated with the SRE event
        """
        self.outputs = outputs
        super().__init__(data=data, state=state)


class EventBacklog(ABC):
    """
    Abstract base class for event backlogs.

    Defines the interface for managing the registration, unregistration, and retrieval of events
    based on their processing state. Subclasses must implement the core methods. The `unregister`
    method is automatically wrapped to prevent misuse with disallowed final states.
    """

    def __init_subclass__(cls, **kwargs: dict) -> None:
        """
        Automatically wraps the subclass's `unregister` method to enforce a state check.

        Wrapping only happens if the subclass explicitly overrides `unregister`.

        Parameters
        ----------
        **kwargs : dict
            Additional keyword arguments passed to the superclass.
        """
        super().__init_subclass__(**kwargs)

        if "unregister" in cls.__dict__:
            original = cls.__dict__["unregister"]

            def guarded_unregister(self, state_type: EventStateType) -> Iterable[Event]:
                """
                Wrapper that enforces allowed final states for `unregister`.

                Raises
                ------
                ValueError
                    If an invalid state is passed.
                """

                if state_type not in (EventStateType.FAILED, EventStateType.ACKED):
                    raise ValueError(
                        f"Invalid state_type: {state_type}, state must be in "
                        f"{(EventStateType.FAILED, EventStateType.ACKED)}"
                    )

                return original(self, state_type)

            setattr(cls, "unregister", guarded_unregister)

    @abstractmethod
    def register(self, events: Iterable[Event]) -> None:
        """
        Register one or more events to the backlog.

        Parameters
        ----------
        events : Iterable[Event]
            An iterable of event instances to be added to the backlog.
        """

    @abstractmethod
    def unregister(self, state_type: EventStateType) -> Iterable[Event]:
        """
        Unregister events from the backlog with the given final state.

        Parameters
        ----------
        state_type : EventStateType
            Final state indicating why the events should be removed.
            Only `FAILED` and `ACKED` are permitted.

        Returns
        -------
        Iterable[Event]
            Events that were unregistered from the backlog.

        Raises
        ------
        ValueError
            If an invalid state is passed (automatically enforced).
        """

    @abstractmethod
    def get(self, state_type: EventStateType) -> Iterable[Event]:
        """
        Retrieve all events currently in the backlog that match a specific processing state.

        Parameters
        ----------
        state_type : EventStateType
            The processing state used to filter events.

        Returns
        -------
        Iterable[Event]
            All events currently in the backlog with the specified state.
        """
