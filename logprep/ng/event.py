# type: ignore
# -> mypy does not correctly handle IntEnum or StrEnum in some cases

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
    """The event was stored in the error output (e.g. error queue or fallback output)."""

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

    >>> state.next()
    <EventStateType.RECEIVED: 'received'>

    >>> state.next()
    <EventStateType.PROCESSING: 'processing'>

    >>> state.next(success=True)
    <EventStateType.PROCESSED: 'processed'>

    >>> state.next()
    <EventStateType.STORED_IN_OUTPUT: 'stored_in_output'>

    >>> state.next(success=False)
    <EventStateType.FAILED: 'failed'>

    >>> state.next()
    <EventStateType.STORED_IN_ERROR: 'stored_in_error'>
    """

    def __init__(self) -> None:
        """Initialize the event state with the default starting state."""

        self.current_state: EventStateType = EventStateType.RECEIVING
        self._state_machine = self._construct_state_machine()

    @staticmethod
    def _construct_state_machine() -> dict[EventStateType, list[EventStateType]]:
        """
        Define the valid state transitions as an adjacency list.

        Returns
        -------
        dict[EventStateType, list[EventStateType]]
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
            EventStateType.STORED_IN_ERROR: [EventStateType.FAILED],
            EventStateType.DELIVERED: [EventStateType.ACKED],
        }

    def next(self, *, success: bool | None = None) -> EventStateType | None:
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
        EventStateType or None
            The new current state after transition, or None if the transition is ambiguous
            or not possible.
        """

        next_states = self._state_machine.get(self.current_state, [])

        if not next_states:
            return None

        if len(next_states) == 1:
            self.current_state = next_states[0]
            return self.current_state

        if success is not None:
            chosen = self._resolve_by_success_flag(next_states, success)
            if chosen:
                self.current_state = chosen
                return self.current_state

        return None

    def _resolve_by_success_flag(
        self, options: list[EventStateType], success: bool
    ) -> EventStateType | None:
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
        EventStateType or None
            The chosen next state, or None if no suitable match was found.
        """

        if success:
            return next(
                (
                    state
                    for state in options
                    if state not in {EventStateType.FAILED, EventStateType.STORED_IN_ERROR}
                ),
                None,
            )
        return next(
            (
                state
                for state in options
                if state in {EventStateType.FAILED, EventStateType.STORED_IN_ERROR}
            ),
            None,
        )

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
