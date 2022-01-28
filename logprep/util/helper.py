"""This module contains helper functions that are shared by different modules."""

from typing import Optional, Union

from colorama import Fore, Back
from colorama.ansi import AnsiFore, AnsiBack


def print_color(back: Optional[AnsiBack], fore: Optional[AnsiFore], message: str):
    """Print string with colors and reset the color afterwards."""
    color = ''
    if back:
        color += back
    if fore:
        color += fore

    print(color + message + Fore.RESET + Back.RESET)


def print_bcolor(back: AnsiBack, message: str):
    """Print string with background color and reset the color afterwards."""
    print_color(back, None, message)


def print_fcolor(fore: AnsiFore, message: str):
    """Print string with colored font and reset the color afterwards."""
    print_color(None, fore, message)


def add_field_to(event, output_field, content, extends_lists=False):
    """
    Add content to an output_field in the given event. Output_field can be a dotted subfield. In case of missing fields
    all intermediate fields will be created.

    Parameters
    ----------
    event: dict
        Original log-event that logprep is currently processing
    output_field: str
        Dotted subfield string indicating the target of the output value, e.g. destination.ip
    content: str, dict
        Value that should be written into the output_field, can be a str or dict object
    extends_lists: bool
        Flag that determines whether or not lists as existing field values should be extended

    Returns
    ------
    This method returns true if no conflicting fields were found during the process of the creation of the dotted
    subfields. If conflicting fields were found False is returned.

    # code is originally from the generic adder, such that duplicated code could be removed there.
    """
    conflicting_fields = list()

    keys = output_field.split('.')
    dict_ = event
    for idx, key in enumerate(keys):
        if key not in dict_:
            if idx == len(keys) - 1:
                dict_[key] = content
                break
            dict_[key] = dict()

        if isinstance(dict_[key], dict) and idx < len(keys) - 1:
            dict_ = dict_[key]
        elif isinstance(dict_[key], list) and extends_lists and idx == len(keys) - 1:
            dict_[key].extend(content)
        else:
            conflicting_fields.append(keys[idx])
            break

    if conflicting_fields:
        return False
    else:
        return True


def get_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
    """
    Returns the value of a requested dotted_field by iterating over the event dictionary until the field was found.
    In case the field could not be found None is returned

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

    # code is originally from the BaseProcessor, such that duplicated code could be removed there.
    """

    fields = dotted_field.split('.')
    dict_ = event
    for field in fields:
        if field in dict_ and isinstance(dict_, dict):
            dict_ = dict_[field]
        else:
            return None
    return dict_
