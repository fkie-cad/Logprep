"""This module contains helper functions that are shared by different modules."""

import itertools
import re
import sys
from functools import lru_cache, partial, reduce
from importlib.metadata import version
from os import remove
from typing import TYPE_CHECKING, Optional, Union

from colorama import Back, Fore
from colorama.ansi import AnsiBack, AnsiFore

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION

if TYPE_CHECKING:  # pragma: no cover
    from logprep.util.configuration import Configuration


def color_print_line(
    back: Optional[Union[str, AnsiBack]], fore: Optional[Union[str, AnsiBack]], message: str
):
    """Print string with colors and reset the color afterwards."""
    color = ""
    if back:
        color += back
    if fore:
        color += fore

    print(color + message + Fore.RESET + Back.RESET)


def color_print_title(background: Union[str, AnsiBack], message: str):
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


def add_field_to_silent_fail(*args, **kwargs):
    try:
        add_field_to(*args, **kwargs)
    except FieldExistsWarning:
        return args[1]


def add_batch_to(event, targets, contents, extends_lists=False, overwrite_output_field=False):
    unsuccessful_targets = map(
        add_field_to_silent_fail,
        itertools.repeat(event, len(targets)),
        targets,
        contents,
        itertools.repeat(extends_lists, len(targets)),
        itertools.repeat(overwrite_output_field, len(targets)),
    )
    unsuccessful_targets = [item for item in unsuccessful_targets if item is not None]
    if unsuccessful_targets:
        raise FieldExistsWarning(event, unsuccessful_targets)


def add_batch_to_silent_fail(*args, **kwargs):
    try:
        add_batch_to(*args, **kwargs)
    except FieldExistsWarning as error:
        return error.skipped_fields


def add_field_to(
    event,
    target_field,
    content,
    extends_lists=False,
    overwrite_output_field=False,
):
    """
    Add content to the output_field in the given event. Output_field can be a dotted subfield.
    In case of missing fields, all intermediate fields will be created.
    Parameters
    ----------
    event: dict
        Original log-event that logprep is currently processing
    target_field: str
        Dotted subfield string indicating the target of the output value, e.g. destination.ip
    content: str, float, int, list, dict
        Value that should be written into the output_field, can be a str, list, or dict object
    extends_lists: bool
        Flag that determines whether output_field lists should be extended
    overwrite_output_field: bool
        Flag that determines whether the output_field should be overwritten
    Raises
    ------
    ValueError
        If both extends_lists and overwrite_output_field are set to True.
    FieldExistsWarning
        If the output field already exists and overwrite_output_field is False, or if extends_lists is True but
        the existing field is not a list.
    """
    if extends_lists and overwrite_output_field:
        raise ValueError("An output field can't be overwritten and extended at the same time")
    field_path = [event, *get_dotted_field_list(target_field)]
    target_key = field_path.pop()

    if overwrite_output_field:
        target_parent = reduce(_add_and_overwrite_key, field_path)
        target_parent[target_key] = content
    else:
        try:
            target_parent = reduce(_add_and_not_overwrite_key, field_path)
        except KeyError as error:
            raise FieldExistsWarning(event, [target_field]) from error
        existing_value = target_parent.get(target_key)
        if existing_value is None:
            target_parent[target_key] = content
            return
        if not extends_lists or not isinstance(existing_value, list):
            raise FieldExistsWarning(event, [target_field])
        if isinstance(content, list):
            target_parent[target_key].extend(content)
        else:
            target_parent[target_key].append(content)


def _get_slice_arg(slice_item):
    return int(slice_item) if slice_item else None


def _get_item(items, item):
    try:
        return dict.__getitem__(items, item)
    except TypeError:
        if ":" in item:
            slice_args = map(_get_slice_arg, item.split(":"))
            item = slice(*slice_args)
        else:
            item = int(item)
        return list.__getitem__(items, item)


def get_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
    """
    Returns the value of a requested dotted_field by iterating over the event dictionary until the
    field was found. In case the field could not be found None is returned.

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
    try:
        for field in get_dotted_field_list(dotted_field):
            event = _get_item(event, field)
        return event
    except (KeyError, ValueError, TypeError, IndexError):
        return None


@lru_cache(maxsize=100000)
def get_dotted_field_list(dotted_field: str) -> list[str]:
    """make lookup of dotted field in the dotted_field_lookup_table and ensures
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


def pop_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
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
    """ensures that the input string is snake_case"""

    _underscorer1 = re.compile(r"(.)([A-Z][a-z]+)")
    _underscorer2 = re.compile("([a-z0-9])([A-Z])")

    subbed = _underscorer1.sub(r"\1_\2", camel)
    return _underscorer2.sub(r"\1_\2", subbed).lower()


def snake_to_camel(snake: str) -> str:
    """ensures that the input string is CamelCase"""

    components = snake.split("_")
    if len(components) == 1:
        camel = components[0]
        return f"{camel[0].upper()}{camel[1:]}"

    camel = "".join(component.title() for component in components)
    return camel


append_as_list = partial(add_field_to, extends_lists=True)


def add_and_overwrite(event, target_field, content, *_):
    """wrapper for add_field_to"""
    add_field_to(event, target_field, content, overwrite_output_field=True)


def add_and_overwrite_silent_fail(event, target_field, content, *_):
    """wrapper for add_field_to"""
    try:
        add_field_to(event, target_field, content, overwrite_output_field=True)
    except FieldExistsWarning:
        ...


def append(event, target_field, content, separator):
    """appends to event"""
    target_value = get_dotted_field_value(event, target_field)
    if not isinstance(target_value, list):
        target_value = "" if target_value is None else target_value
        target_value = f"{target_value}{separator}{content}"
        add_and_overwrite(event, target_field, target_value)
    else:
        append_as_list(event, target_field, content)


def get_source_fields_dict(event, rule):
    """returns a dict with dotted fields as keys and target values as values"""
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
