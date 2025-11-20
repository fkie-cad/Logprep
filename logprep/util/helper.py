"""This module contains helper functions that are shared by different modules."""

import itertools
import re
import sys
from enum import Enum, auto
from functools import lru_cache, partial, reduce
from importlib.metadata import version
from os import remove
from typing import TYPE_CHECKING, Callable, Iterable, Optional, TypeAlias, Union, cast

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.ansi import AnsiBack, AnsiFore, Back, Fore
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION

if TYPE_CHECKING:  # pragma: no cover
    from logprep.processor.base.rule import Rule
    from logprep.util.configuration import Configuration


class Missing(Enum):
    """Sentinel type for indicating missing fields."""

    MISSING = auto()


MISSING = Missing.MISSING  # pylint: disable=invalid-name
"""Sentinel value for indicating missing fields."""


class Skip(Enum):
    """Sentinel type for method instrumentation to skip fields."""

    SKIP = auto()


SKIP = Skip.SKIP  # pylint: disable=invalid-name
"""Sentinel value for method instrumentation to skip fields."""


FieldValue: TypeAlias = Union[
    dict[str, "FieldValue"], list["FieldValue"], str, int, float, bool, None
]


def color_print_line(back: str | AnsiBack | None, fore: str | AnsiBack | None, message: str):
    """Print string with colors and reset the color afterwards."""
    color = ""
    if back:
        color += back
    if fore:
        color += fore

    print(color + message + Fore.RESET + Back.RESET)


def color_print_title(background: str | AnsiBack, message: str):
    """Print dashed title line with black foreground colour and reset the color afterwards."""
    message = f"------ {message} ------"
    color_print_line(background, Fore.BLACK, message)


def print_fcolor(fore: AnsiFore, message: str):
    """Print string with colored font and reset the color afterwards."""
    color_print_line(None, fore, message)


def _add_and_overwrite_key(sub_dict, key):
    current_value = sub_dict.get(key)
    if isinstance(current_value, dict):
        return current_value
    sub_dict.update({key: {}})
    return sub_dict.get(key)


def _add_and_not_overwrite_key(sub_dict, key):
    current_value = sub_dict.get(key)
    if isinstance(current_value, dict):
        return current_value
    if key in sub_dict:
        raise KeyError("key exists")
    sub_dict.update({key: {}})
    return sub_dict.get(key)


def _add_field_to(
    event: dict,
    field: tuple,
    rule: Optional["Rule"],
    merge_with_target: bool = False,
    overwrite_target: bool = False,
) -> None:
    """
    Add content to the target_field in the given event. target_field can be a dotted subfield.
    In case of missing fields, all intermediate fields will be created.

    Parameters
    ----------
    event: dict
        Original log-event that logprep is currently processing
    field: tuple
        A key value pair describing the field that should be added. The key is the dotted subfield string
        indicating the target. The value is the content that should be added to the named target.
        The content can be of type str, float, int, list, dict.
    rule: Rule
        A rule that initiated the field addition, is used for proper error handling.
    merge_with_target: bool, optional
        Flag that determines whether the content should be merged with an existing target_field.
        Defaults to False.
    overwrite_target: bool, optional
        Flag that determines whether the target_field should be overwritten by content.
        Defaults to False.

    Raises
    ------
    FieldExistsWarning
        If the target_field already exists and overwrite_target_field is False,
        or if extends_lists is True but the existing field is not a list.
    """
    if merge_with_target and overwrite_target:
        raise ValueError("Can't merge with and overwrite a target field at the same time")
    target_field, content = field
    field_path = [event, *get_dotted_field_list(target_field)]
    target_key = field_path.pop()

    if overwrite_target:
        target_parent = reduce(_add_and_overwrite_key, field_path)
        target_parent[target_key] = content
        return
    try:
        target_parent = reduce(_add_and_not_overwrite_key, field_path)
    except KeyError as error:
        raise FieldExistsWarning(rule, event, [target_field]) from error
    existing_value = target_parent.get(target_key)
    if existing_value is None:
        target_parent[target_key] = content
        return
    if not merge_with_target:
        raise FieldExistsWarning(rule, event, [target_field])
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
            raise FieldExistsWarning(rule, event, [target_field])
        target_parent[target_key] = [existing_value, content]


def _add_field_to_silent_fail(*args, **kwargs) -> None | str:
    """
    Adds a field to an object, ignoring the FieldExistsWarning if the field already exists.
    Is only needed in the add_batch_to map function. Without this, the map would terminate early.

    Parameters
    ----------
        args: tuple
            Positional arguments to pass to the add_field_to function.
        kwargs: dict
            Keyword arguments to pass to the add_field_to function.

    Returns
    -------
        The field that was attempted to be added, if the field already exists.
    """
    try:
        _add_field_to(*args, **kwargs)
    except FieldExistsWarning as error:
        return error.skipped_fields[0]
    return None


def add_fields_to(
    event: dict,
    fields: dict,
    rule: Optional["Rule"] = None,
    merge_with_target: bool = False,
    overwrite_target: bool = False,
    skip_none: bool = True,
) -> None:
    """
    Handles the batch addition operation while raising a FieldExistsWarning with
    all unsuccessful targets.

    Parameters
    ----------
        event: dict
            The event object to which fields are to be added.
        fields: dict
            A dict with key value pairs describing the fields that should be added.
            The key is the dotted subfield string indicating the target.
            The value is the content that should be added to the named target.
            The content can be of type: str, float, int, list, dict.
        rule: Rule, optional
            A rule that initiated the field addition, is used for proper error handling.
        merge_with_target: bool, optional
            A boolean indicating whether to merge if the target field already exists.
            Defaults to False.
        overwrite_target: bool, optional
            A boolean indicating whether to overwrite the target field if it already exists.
            Defaults to False.
        skip_none: bool, optional
            A boolean indicating whether to filter out None-valued fields. Defaults to True.

    Raises
    ------
        FieldExistsWarning: If there are targets to which the content could not be added due to
        field existence restrictions.
    """
    # filter out None values
    fields = {key: value for key, value in fields.items() if not skip_none or value is not None}
    number_fields = len(dict(fields))
    if number_fields == 1:
        _add_field_to(event, list(fields.items())[0], rule, merge_with_target, overwrite_target)
        return
    unsuccessful_targets = map(
        _add_field_to_silent_fail,
        itertools.repeat(event, number_fields),
        fields.items(),
        itertools.repeat(rule, number_fields),
        itertools.repeat(merge_with_target, number_fields),
        itertools.repeat(overwrite_target, number_fields),
    )
    unsuccessful_targets_resolved = [item for item in unsuccessful_targets if item is not None]
    if unsuccessful_targets_resolved:
        raise FieldExistsWarning(rule, event, unsuccessful_targets_resolved)


def _get_slice_arg(slice_item) -> int | None:
    return int(slice_item) if slice_item else None


def _get_item(container: FieldValue, key: str) -> FieldValue:
    """
    Retrieves the value associated with given key from the container.

    This function supports:
    - Getting a value by name from a dict ({ "K": X }, "K") -> X
    - Getting a value by index from a list ([X, Y, Z], "1") -> Y
    - Getting a value by slice from a list ([X, Y, Z], "1:") -> [Y, Z]

    The retrieved value itself can be a container type,
    thus this function can be used to traverse a nested data structure.

    Parameters
    ----------
    container : FieldValue
        Container object where data is read from
    key : str
        Dictionary key, index or slice spec refering to the container

    Returns
    -------
    FieldValue
        The container value which is referenced by the key

    Raises
    ------
    KeyError
        The container is a dict, but key does not exist in it
    IndexError
        The container is a list, but key does not represent a valid index in it
    ValueError
        The container is not a dict, but key is neither slice nor integer index
    TypeError
        The key is not a valid slice or the container is neither a dict nor a list
    """
    try:
        return dict.__getitem__(cast(dict[str, FieldValue], container), key)
    except TypeError:
        index_or_slice: slice | int
        if ":" in key:
            slice_args = map(_get_slice_arg, key.split(":"))
            index_or_slice = slice(*slice_args)
        else:
            index_or_slice = int(key)
        return list.__getitem__(cast(list[FieldValue], container), index_or_slice)


def get_dotted_field_value(event: dict[str, FieldValue], dotted_field: str) -> FieldValue:
    """
    Returns the value of a requested dotted_field by iterating over the event dictionary until the
    field was found. In case the field could not be found None is returned.

    Parameters
    ----------
    event: dict[str, FieldValue]
        The event from which the dotted field value should be extracted
    dotted_field: str
        The dotted field name which identifies the requested value

    Returns
    -------
    FieldValue
        The value of the requested dotted field, which can be None.
        None is also returnd when the field could not be found and silent_fail is True.

    Raises
    ------
    KeyError, ValueError, TypeError, IndexError
        Different errors which can be raised on missing fields and silent_fail is False.
    """
    current: FieldValue = event
    try:
        for field in get_dotted_field_list(dotted_field):
            current = _get_item(current, field)
        return current
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def get_dotted_field_value_with_explicit_missing(
    event: dict[str, FieldValue], dotted_field: str
) -> FieldValue | Missing:
    """
    Returns the value of a requested dotted_field by iterating over the event dictionary until the
    field was found. In case the field could not be found None is returned.

    Parameters
    ----------
    event: dict[str, FieldValue]
        The event from which the dotted field value should be extracted
    dotted_field: str
        The dotted field name which identifies the requested value

    Returns
    -------
    FieldValue | Missing
        The value of the requested dotted field, which can be None.
        None is also returnd when the field could not be found and silent_fail is True.

    Raises
    ------
    KeyError, ValueError, TypeError, IndexError
        Different errors which can be raised on missing fields and silent_fail is False.
    """
    current: FieldValue = event
    try:
        for field in get_dotted_field_list(dotted_field):
            current = _get_item(current, field)
        return current
    except (KeyError, ValueError, TypeError, IndexError):
        return MISSING


def get_dotted_field_values(
    event: dict,
    dotted_fields: Iterable[str],
    on_missing: Callable[[str], FieldValue | Skip] = lambda _: None,
) -> dict[str, FieldValue]:
    """
    Extract the subset of fields from the dict by using the list of (potentially dotted)
    field names as an allow list.
    The behavior for fields targeted by the list but missing in the dict can be controlled
    by a callback.
    The callback allows for providing a replacement value, or - by returning SKIP - can
    instruct the method to omit the field entirely from the extracted dict.


    Parameters
    ----------
    event : dict
        The (potentially nested) dict where the values are sourced from
    dotted_fields : Iterable[str]
        The (potentially dotted) list of field names to extract
    on_missing : Callable[[str], FieldValue | Skip], optional
        The callback to control the behavior for missing fields, by default
        `lambda _: None` which returns missing fields with `None` value

    Returns
    -------
    dict[str, FieldValue]
        The (potentially nested) sub-dict
    """
    result: dict[str, FieldValue] = {}
    for field_to_copy in dotted_fields:
        value = get_dotted_field_value_with_explicit_missing(event, field_to_copy)
        if value is MISSING:
            value = on_missing(field_to_copy)
            if value is SKIP:
                continue
        result[field_to_copy] = value
    return result


@lru_cache(maxsize=100000)
def get_dotted_field_list(dotted_field: str) -> list[str]:
    """Make lookup of dotted field in the dotted_field_lookup_table and ensures
    it is added if not found. Additionally, the string will be interned for faster
    followup lookups.

    Parameters
    ----------
    dotted_field : str
        the dotted field input

    Returns
    -------
    list[str]
        a list with keys for dictionary iteration
    """
    return dotted_field.split(".")


def pop_dotted_field_value(event: dict, dotted_field: str) -> FieldValue:
    """
    Remove and return dotted field. Returns None is field does not exist.

    Parameters
    ----------
    event: dict
        The event from which the dotted field value should be extracted
    dotted_field: str
        The dotted field name which identifies the requested value

    Returns
    -------
    dict_: dict, list, str
        The value of the requested dotted field.
    """
    fields = dotted_field.split(".")
    return _retrieve_field_value_and_delete_field_if_configured(
        event, fields, delete_source_field=True
    )


def _retrieve_field_value_and_delete_field_if_configured(
    sub_dict, dotted_fields_path, delete_source_field=False
):
    """
    Iterates recursively over the given dictionary retrieving the dotted field. If set the source
    field will be removed. When again going back up the stack trace it deletes the empty left over
    dicts.
    """
    next_key = dotted_fields_path.pop(0)
    if next_key in sub_dict and isinstance(sub_dict, dict):
        if not dotted_fields_path:
            field_value = sub_dict[next_key]
            if delete_source_field:
                del sub_dict[next_key]
            return field_value
        field_value = _retrieve_field_value_and_delete_field_if_configured(
            sub_dict[next_key], dotted_fields_path, delete_source_field
        )
        # If remaining subdict is empty delete it
        if not sub_dict[next_key]:
            del sub_dict[next_key]
        return field_value
    return None


def recursive_compare(test_output, expected_output):
    """Recursively compares given test_output against an expected output."""
    result = None

    if not isinstance(test_output, type(expected_output)):
        return test_output, expected_output

    if isinstance(test_output, dict) and isinstance(expected_output, dict):
        if sorted(test_output.keys()) != sorted(expected_output.keys()):
            return sorted(test_output.keys()), sorted(expected_output.keys())

        for key in test_output.keys():
            result = recursive_compare(test_output[key], expected_output[key])
            if result:
                return result

    elif isinstance(test_output, list) and isinstance(expected_output, list):
        for index, _ in enumerate(test_output):
            result = recursive_compare(test_output[index], expected_output[index])
            if result:
                return result

    else:
        if test_output != expected_output:
            result = test_output, expected_output

    return result


def remove_file_if_exists(test_output_path):
    """Remove existing file."""
    try:
        remove(test_output_path)
    except FileNotFoundError:
        pass


def camel_to_snake(camel: str) -> str:
    """Ensures that the input string is snake_case"""

    _underscorer1 = re.compile(r"(.)([A-Z][a-z]+)")
    _underscorer2 = re.compile("([a-z0-9])([A-Z])")

    subbed = _underscorer1.sub(r"\1_\2", camel)
    return _underscorer2.sub(r"\1_\2", subbed).lower()


def snake_to_camel(snake: str) -> str:
    """Ensures that the input string is CamelCase"""

    components = snake.split("_")
    if len(components) == 1:
        camel = components[0]
        return f"{camel[0].upper()}{camel[1:]}"

    camel = "".join(component.title() for component in components)
    return camel


append_as_list = partial(add_fields_to, merge_with_target=True)


def copy_fields_to_event(
    target_event: dict,
    source_event: dict,
    dotted_field_names: Iterable[str],
    *,
    skip_missing: bool = True,
    merge_with_target: bool = False,
    overwrite_target: bool = False,
    rule: Optional["Rule"] = None,
) -> None:
    """
    Copies fields from source_event to target_event.
    The function behaves similar to add_fields_to.

    Parameters
    ----------
    target_event : dict
        The field dictionary where fields are being added to in-place
    source_event : dict
        The field dictionary where field values are being read from
    dotted_field_names : Iterable[str]
        The list of (potentially dotted) field names to copy
    skip_missing : bool, optional
        Controls whether missing fields should be skipped or defaulted to None, by default True
    merge_with_target : bool, optional
        Controls whether already existing fields should be merged as a list, by default False
    overwrite_target : bool, optional
        Controls whether already existing fields should be overwritten, by default False
    rule : Rule, optional
        Contextual info for error handling, by default None
    """
    on_missing_result = SKIP if skip_missing else None
    source_fields = get_dotted_field_values(
        source_event, dotted_field_names, on_missing=lambda _: on_missing_result
    )
    add_fields_to(
        target_event,
        source_fields,
        rule=rule,
        overwrite_target=overwrite_target,
        merge_with_target=merge_with_target,
        skip_none=False,
    )


def add_and_overwrite(event, fields, rule, *_):
    """Wrapper for add_field_to"""
    add_fields_to(event, fields, rule, overwrite_target=True)


def append(event, field, separator, rule):
    """Appends to event"""
    target_field, content = list(field.items())[0]
    target_value = get_dotted_field_value(event, target_field)
    if not isinstance(target_value, list):
        target_value = "" if target_value is None else target_value
        target_value = f"{target_value}{separator}{content}"
        add_and_overwrite(event, fields={target_field: target_value}, rule=rule)
    else:
        append_as_list(event, field)


def get_source_fields_dict(event, rule):
    """Returns a dict with dotted fields as keys and target values as values"""
    source_fields = rule.source_fields
    source_field_values = map(partial(get_dotted_field_value, event), source_fields)
    source_field_dict = dict(zip(source_fields, source_field_values))
    return source_field_dict


def get_versions_string(config: "Configuration" = None) -> str:
    """
    Prints the version and exists. If a configuration was found then it's version
    is printed as well
    """
    padding = 25
    version_string = f"{'python version:'.ljust(padding)}{sys.version.split()[0]}"
    version_string += f"\n{'logprep version:'.ljust(padding)}{version('logprep')}"
    if config:
        config_version = (
            f"{config.version}, {', '.join(config.config_paths) if config.config_paths else 'None'}"
        )
    else:
        config_version = f"no configuration found in {', '.join([DEFAULT_CONFIG_LOCATION])}"
    version_string += f"\n{'configuration version:'.ljust(padding)}{config_version}"
    return version_string
