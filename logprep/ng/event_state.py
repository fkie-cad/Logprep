"""The event classes and related types"""

from enum import StrEnum


class EventStateType(StrEnum):
    """Event states representing the lifecycle of a log event."""

    RECEIVING = "receiving"
    """The event is being received (e.g. from input connector)."""

    RECEIVED = "received"
    """The event has been successfully received."""

    PROCESSING = "processing"
    """The event is currently being processed by the pipeline."""

    PROCESSED = "processed"
    """The event has been processed by all pipeline processors."""

    STORED_IN_OUTPUT = "stored_in_output"
    """The event was successfully stored in the output connector."""

    FAILED = "failed"
    """The event failed during processing or output storage."""

    STORED_IN_ERROR = "stored_in_error"
    """The event was stored in the error output (e.g. error queue or
    fallback output)."""

    DELIVERED = "delivered"
    """The event was delivered to the target system or final destination."""

    ACKED = "acked"
    """The event was acknowledged by the downstream system or consumer."""


class EventState:
    """
    Manages the lifecycle of a log event using a finite state machine.

    This class encapsulates valid transitions between event states such as
    receiving, processing, delivery, and failure handling. It supports
    automatic and conditional transitions based on success flags.

    Examples
    --------
    >>> state = EventState()
    >>> state.current_state
    <EventStateType.RECEIVING: 'receiving'>

    >>> state.next_state()
    <EventStateType.RECEIVED: 'received'>

    >>> state.next_state()
    <EventStateType.PROCESSING: 'processing'>

    >>> state.next_state(success=True)
    <EventStateType.PROCESSED: 'processed'>

    >>> state.next_state()
    <EventStateType.STORED_IN_OUTPUT: 'stored_in_output'>

    >>> state.next_state(success=False)
    <EventStateType.FAILED: 'failed'>

    >>> state.next_state()
    <EventStateType.STORED_IN_ERROR: 'stored_in_error'>

    >>> state.next_state(success=True)
    <EventStateType.DELIVERED: 'delivered'>
    """

    _FAILURE_STATES = {EventStateType.FAILED, EventStateType.STORED_IN_ERROR}
    _SUCCESS_STATES = {
        EventStateType.RECEIVED,
        EventStateType.PROCESSING,
        EventStateType.PROCESSED,
        EventStateType.STORED_IN_OUTPUT,
        EventStateType.DELIVERED,
        EventStateType.ACKED,
    }

    _state_machine: dict[str, list[str]] = {}  # Will be initialized lazily
    """Class-level state transition map, initialized once and shared across
    all instances."""

    def __init__(self) -> None:
        """Initialize the event state with the default starting state."""

        if not EventState._state_machine:
            EventState._state_machine = EventState._construct_state_machine()

        self.current_state: str = EventStateType.RECEIVING

    @staticmethod
    def _construct_state_machine() -> dict[str, list[str]]:
        """
        Define the valid state transitions as an adjacency list.

        Returns
        -------
        dict[EventStateType, list[str]]
            A dictionary mapping each state to its allowed successor states.
        """

        return {
            EventStateType.RECEIVING: [EventStateType.RECEIVED],
            EventStateType.RECEIVED: [EventStateType.PROCESSING],
            EventStateType.PROCESSING: [
                EventStateType.FAILED,
                EventStateType.PROCESSED,
            ],
            EventStateType.PROCESSED: [EventStateType.STORED_IN_OUTPUT],
            EventStateType.STORED_IN_OUTPUT: [
                EventStateType.FAILED,
                EventStateType.DELIVERED,
            ],
            EventStateType.FAILED: [EventStateType.STORED_IN_ERROR],
            EventStateType.STORED_IN_ERROR: [
                EventStateType.FAILED,
                EventStateType.DELIVERED,
            ],
            EventStateType.DELIVERED: [EventStateType.ACKED],
        }

    def next_state(self, *, success: bool | None = None) -> str:
        """
        Advance to the next logical state based on the current state.

        If there is exactly one valid next state, it will be chosen automatically.
        If multiple transitions are possible (e.g. success vs. failure), the `success`
        parameter can be used to resolve the path.

        Parameters
        ----------
        success : bool, optional
            If provided, determines the outcome path in ambiguous transitions.
            - True: prefer successful path
            - False: prefer failure path

        Returns
        -------
        EventStateType
            The new current state after transition.

        Raises
        ------
        ValueError
            If the current state has no defined next transitions or if the transition
            is ambiguous and `success` is not provided.
        """

        next_states = self._state_machine.get(self.current_state)

        if not next_states:
            raise ValueError("Invalid state transition: Already reached terminal state")

        if len(next_states) == 1:
            self.current_state = next_states[0]
            return self.current_state

        if success is not None:
            chosen = self._resolve_by_success_flag(next_states, success)

            if chosen:
                self.current_state = chosen
                return self.current_state

        raise ValueError("Invalid state transition: Ambiguous event without success.")

    @classmethod
    def _resolve_by_success_flag(cls, options: list[str], success: bool) -> str | None:
        """
        Resolve a path when multiple options are available based on success.

        Parameters
        ----------
        options : list of EventStateType
            Available next states.
        success : bool
            Outcome of the current step to choose the proper next state.

        Returns
        -------
        str or None
            The chosen next state, or None if no suitable match was found.
        """

        candidates = cls._SUCCESS_STATES if success else cls._FAILURE_STATES
        return next((state for state in options if state in candidates), None)

    def reset(self) -> None:
        """Reset the event state to the initial state (RECEIVING)."""

        self.current_state = EventStateType.RECEIVING

    def __str__(self) -> str:
        """
        Return a string representation of the current event state.

        Returns
        -------
        str
            A string like "<EventState: current_state>".
        """

        return f"<EventState: {self.current_state}>"
