# pylint: disable=too-few-public-methods

"""abstract module for event"""

from abc import ABC
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional

from attrs import define, field, validators

from logprep.util.helper import (
    FieldValue,
    Missing,
    add_fields_to,
    get_dotted_field_value,
    pop_dotted_field_value,
)

if TYPE_CHECKING:  # pragma: no cover
    from logprep.processor.base.rule import Rule


class EventMetadata(ABC):
    """Abstract EventMetadata Class to define the Interface"""

    @staticmethod
    def from_dict(_: dict):
        """
        Constructs a metadata object from the given dict.
        Currently implemented as a placeholder for future development.
        """
        return EventMetadata()


class Event(ABC):
    """
    Abstract base class representing an event in the processing pipeline.

    Encapsulates data, warnings and errors.
    """

    __slots__: tuple[str, ...] = ("data", "errors", "warnings")

    def __init__(self, data: dict[str, Any]) -> None:
        """
        Initialize an Event instance.

        Parameters
        ----------
        data : dict[str, Any]
            The raw or processed data associated with the event.
        """
        self.data: dict[str, Any] = data
        self.errors: list[Exception] = []
        self.warnings: list[Exception] = []
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
        return f"{self.__class__.__name__}(data={self.data})"

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
        rule: Optional["Rule"] = None,
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

    def pop_dotted_field_value(self, dotted_field: str) -> FieldValue | Missing:
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


@define
class OutputSpec:
    """
    Specifies an output by name and which target (e.g. topic for kafka, index for opensearch) should be addressed.
    """

    output_name: str = field(validator=(validators.instance_of(str), validators.min_len(1)))
    output_target: str = field(validator=(validators.instance_of(str), validators.min_len(1)))


class ExtraDataEvent(Event):
    """
    Abstract base class for events that can contain extra data.

    This class extends the basic Event functionality to include a list of
    additional Event instances that are related to this event.
    """

    __slots__ = ("outputs",)

    outputs: Sequence[OutputSpec]

    def __init__(
        self,
        data: dict[str, str],
        *,
        outputs: Sequence[OutputSpec],
    ) -> None:
        """
        Parameters
        ----------
        data : dict[str, str]
            The main data payload for the SRE event.
        outputs : Sequence[OutputSpec]
            The collection of output connector names associated with the SRE event
        """
        self.outputs = outputs
        super().__init__(data=data)
