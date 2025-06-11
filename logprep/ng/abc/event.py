# pylint: disable=too-few-public-methods

"""abstract module for event"""

import itertools
from abc import ABC
from functools import lru_cache, reduce
from typing import Any

from logprep.ng.event_state import EventState
from logprep.processor.base.exceptions import FieldExistsWarning


class EventMetadata(ABC):
    """Abstract EventMetadata Class to define the Interface"""


class Event(ABC):
    """
    Abstract base class representing an event in the processing pipeline.

    This class encapsulates event-related data, warnings, errors,
    and its current processing state via a state machine.

    Parameters
    ----------
    data : dict[str, Any]
        The raw or processed data associated with the event.
    state : EventState, optional (keyword-only)
        The initial state of the event. If not provided, defaults to `EventState()`.

    Attributes
    ----------
    data : dict[str, Any]
        The actual payload or metadata of the event.
    state : EventState
        Tracks the current state of the event lifecycle.
    warnings : list[str]
        Collected warnings during event handling or transformation.
    errors : list[Exception]
        Collected errors encountered while processing the event.

    Examples
    --------
    >>> event = Event({"source": "syslog"})
    >>> event.state.current_state
    <EventStateType.RECEIVING: 'receiving'>

    >>> event_with_state = Event({"source": "api"}, state=EventState())
    >>> isinstance(event_with_state.state, EventState)
    True
    """

    __slots__: tuple[str, ...] = ("data", "state", "errors", "warnings")

    def __init__(
        self,
        data: dict[str, Any],
        *,
        state: EventState | None = None,
    ) -> None:
        self.state: EventState = EventState() if state is None else state
        self.data: dict[str, Any] = data
        self.warnings: list[str] = []
        self.errors: list[Exception] = []
        super().__init__()

    def _add_and_overwrite_key(self, sub_dict, key):
        current_value = sub_dict.get(key)
        if isinstance(current_value, dict):
            return current_value
        sub_dict.update({key: {}})
        return sub_dict.get(key)

    def _add_and_not_overwrite_key(self, sub_dict, key):
        current_value = sub_dict.get(key)
        if isinstance(current_value, dict):
            return current_value
        if key in sub_dict:
            raise KeyError("key exists")
        sub_dict.update({key: {}})
        return sub_dict.get(key)

    def _add_field_to(
        self,
        field: tuple,
        rule: "Rule",
        merge_with_target: bool = False,
        overwrite_target: bool = False,
    ) -> None:
        """
        Add content to the target_field in the event. Intermediate fields
        are created if missing.

        Raises FieldExistsWarning if target exists and overwrite/merge
            is not allowed.
        """

        if merge_with_target and overwrite_target:
            raise ValueError("Can't merge with and overwrite a target field at the same time")

        target_field, content = field
        field_path = [self.data, *self.get_dotted_field_list(target_field)]
        target_key = field_path.pop()

        if overwrite_target:
            target_parent = reduce(self._add_and_overwrite_key, field_path)
            target_parent[target_key] = content
            return

        try:
            target_parent = reduce(self._add_and_not_overwrite_key, field_path)
        except KeyError as error:
            raise FieldExistsWarning(rule, self.data, [target_field]) from error

        existing_value = target_parent.get(target_key)

        if existing_value is None:
            target_parent[target_key] = content
            return

        if not merge_with_target:
            raise FieldExistsWarning(rule, self.data, [target_field])

        if isinstance(existing_value, dict) and isinstance(content, dict):
            existing_value.update(content)
            target_parent[target_key] = existing_value
        elif isinstance(existing_value, list) and isinstance(content, list):
            existing_value.extend(content)
            target_parent[target_key] = existing_value
        elif isinstance(existing_value, list) and isinstance(content, (int, float, str, bool)):
            target_parent[target_key] = existing_value + [content]
        elif isinstance(existing_value, (int, float, str, bool)) and isinstance(content, list):
            target_parent[target_key] = [existing_value] + content
        else:
            if not overwrite_target:
                raise FieldExistsWarning(rule, self.data, [target_field])
            target_parent[target_key] = [existing_value, content]

    def _add_field_to_silent_fail(self, *args, **kwargs) -> str | None:
        """
        Adds a field while suppressing FieldExistsWarning.
        Returns the skipped field if warning is raised.
        """

        try:
            self._add_field_to(*args, **kwargs)
        except FieldExistsWarning as error:
            return error.skipped_fields[0]

        return None

    def add_fields_to(
        self,
        fields: dict,
        rule: "Rule" = None,
        merge_with_target: bool = False,
        overwrite_target: bool = False,
    ) -> None:
        """
        Handles batch field addition to the event. Raises FieldExistsWarning
        with list of skipped fields.
        """

        fields = {key: value for key, value in fields.items() if value is not None}
        number_fields = len(fields)

        if number_fields == 1:
            self._add_field_to(
                list(fields.items())[0],
                rule,
                merge_with_target,
                overwrite_target,
            )
            return

        unsuccessful_targets = map(
            self._add_field_to_silent_fail,
            fields.items(),
            itertools.repeat(rule, number_fields),
            itertools.repeat(merge_with_target, number_fields),
            itertools.repeat(overwrite_target, number_fields),
        )
        unsuccessful_targets_resolved = [item for item in unsuccessful_targets if item is not None]

        if unsuccessful_targets_resolved:
            raise FieldExistsWarning(rule, self.data, unsuccessful_targets_resolved)

    def _get_slice_arg(self, slice_item):
        return int(slice_item) if slice_item else None

    def _get_item(self, items, item):
        """
        Internal helper for dict or list access by index or slice.
        """

        try:
            return dict.__getitem__(items, item)
        except TypeError:
            if ":" in item:
                slice_args = map(self._get_slice_arg, item.split(":"))
                item = slice(*slice_args)
            else:
                item = int(item)

            return list.__getitem__(items, item)

    def get_dotted_field_value(self, dotted_field: str) -> dict | list | str | None:
        """
        Returns the value of a dotted_field by iterating through the event.
        Returns None if the field is not found.
        """

        try:
            current = self.data

            for field in self.get_dotted_field_list(dotted_field):
                current = self._get_item(current, field)
            return current

        except (KeyError, ValueError, TypeError, IndexError):
            return None

    def pop_dotted_field_value(self, dotted_field: str) -> dict | list | str | None:
        """
        Removes and returns a dotted field from the event. Cleans up empty intermediate dicts.
        """

        fields = dotted_field.split(".")

        return self._retrieve_field_value_and_delete_field_if_configured(
            self.data, fields, delete_source_field=True
        )

    def _retrieve_field_value_and_delete_field_if_configured(
        self,
        sub_dict,
        dotted_fields_path,
        delete_source_field=False,
    ):
        """
        Recursive retrieval of a dotted field with optional deletion.
        """

        next_key = dotted_fields_path.pop(0)

        if next_key in sub_dict and isinstance(sub_dict, dict):
            if not dotted_fields_path:
                field_value = sub_dict[next_key]

                if delete_source_field:
                    del sub_dict[next_key]

                return field_value

            field_value = self._retrieve_field_value_and_delete_field_if_configured(
                sub_dict[next_key], dotted_fields_path, delete_source_field
            )

            if not sub_dict[next_key]:
                del sub_dict[next_key]

            return field_value
        return None

    @lru_cache(maxsize=100000)
    def get_dotted_field_list(self, dotted_field: str) -> list[str]:
        """
        Splits a dotted field path into a list of keys for dictionary iteration.
        """

        return dotted_field.split(".")
