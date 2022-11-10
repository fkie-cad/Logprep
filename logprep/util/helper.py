"""This module contains helper functions that are shared by different modules."""
import re
from functools import partial, reduce
from os import remove
from typing import Optional, Union

from colorama import Fore, Back
from colorama.ansi import AnsiFore, AnsiBack


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


def add_field_to(event, output_field, content, extends_lists=False, overwrite_output_field=False):
    """
    Add content to an output_field in the given event. Output_field can be a dotted subfield.
    In case of missing fields all intermediate fields will be created.
    Parameters
    ----------
    event: dict
        Original log-event that logprep is currently processing
    output_field: str
        Dotted subfield string indicating the target of the output value, e.g. destination.ip
    content: str, list, dict
        Value that should be written into the output_field, can be a str, list or dict object
    extends_lists: bool
        Flag that determines whether output_field lists should be extended
    overwrite_output_field: bool
        Flag that determines whether the output_field should be overwritten

    Returns
    ------
    This method returns true if no conflicting fields were found during the process of the creation
    of the dotted subfields. If conflicting fields were found False is returned.
    """

    assert not (
        extends_lists and overwrite_output_field
    ), "An output field can't be overwritten and extended at the same time"

    output_field_path = [event, *output_field.split(".")]
    target_key = output_field_path.pop()

    if overwrite_output_field:
        target_field = reduce(_add_and_overwrite_key, output_field_path)
        target_field.update({target_key: content})
        return True

    try:
        target_field = reduce(_add_and_not_overwrite_key, output_field_path)
    except KeyError:
        return False

    target_field_value = target_field.get(target_key)
    if target_field_value is None:
        target_field.update({target_key: content})
        return True
    if extends_lists:
        if not isinstance(target_field_value, list):
            return False
        if isinstance(content, list):
            target_field.update({target_key: [*target_field_value, *content]})
        else:
            target_field_value.append(content)
        return True
    return False


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

    fields = [event, *dotted_field.split(".")]
    try:
        return reduce(dict.__getitem__, fields)
    except KeyError:
        return None
    except TypeError:
        return None


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


def append(event, target_field, content, separator):
    """appends to event"""
    target_value = get_dotted_field_value(event, target_field)
    if isinstance(target_value, str):
        separator = " " if separator is None else separator
        target_value = f"{target_value}{separator}{content}"
        add_and_overwrite(event, target_field, target_value)
    else:
        append_as_list(event, target_field, content)
