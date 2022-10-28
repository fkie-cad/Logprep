""" validators to use with `attrs` fields"""
import os
import typing
from urllib.parse import urlparse

from logprep.factory_error import InvalidConfigurationError
from logprep.util.json_handling import is_json


def json_validator(_, __, value):
    """validate if a file is valid json"""
    if not is_json(value):
        raise InvalidConfigurationError(f"`{value}` is not valid json")


def file_validator(_, attribute, value):
    """validate if an attribute is a valid file"""
    if attribute.default is None and value is None:
        return
    if not isinstance(value, str):
        raise InvalidConfigurationError(f"{attribute.name} is not a str")
    if not os.path.exists(value):
        raise InvalidConfigurationError(f"{attribute.name} file '{value}' does not exist")
    if not os.path.isfile(value):
        raise InvalidConfigurationError(f"{attribute.name} '{value}' is not a file")


def directory_validator(_, attribute, value):
    """validate if an attribute is a valid directory"""
    if attribute.default is None and value is None:
        return
    if not isinstance(value, str):
        raise InvalidConfigurationError(f"{attribute.name} is not a str")
    if not os.path.exists(value):
        raise InvalidConfigurationError(f"{attribute.name} file '{value}' does not exist")
    if not os.path.isdir(value):
        raise InvalidConfigurationError(f"{attribute.name} '{value}' is not a directory")


def url_validator(_, attribute, value):
    """
    Validate if a str has url like pattern. If it starts with file:// the file_validator
    is called instead.
    """
    if attribute.default is None and value is None:
        return
    if not isinstance(value, str):
        raise InvalidConfigurationError(f"{attribute.name} is not a str")
    parsed_url = urlparse(value)
    if not parsed_url.scheme and not parsed_url.netloc and not parsed_url.path:
        raise InvalidConfigurationError(f"{attribute.name} has no schema, net location and path")
    if not parsed_url.scheme and not parsed_url.netloc and parsed_url.path:
        file_validator(_, attribute, value)
    if parsed_url.scheme == "file":
        if parsed_url.params or parsed_url.query or parsed_url.fragment:
            raise InvalidConfigurationError(f"{attribute.name} has malformed file location")
        value = f"{parsed_url.netloc}{parsed_url.path}"
        file_validator(_, attribute, value)


def is_non_empty_list_validator(attribute, given_list):
    """Validates if a argument is a non empty list"""
    if not isinstance(given_list, list):
        raise InvalidConfigurationError(f"{attribute.name} is not a list")
    if len(given_list) == 0:
        raise InvalidConfigurationError(f"{attribute.name} is empty list")


def list_of_urls_validator(_, attribute, url_list):
    """validate if a list has valid urls"""
    if attribute.default is None and url_list is None:
        return
    is_non_empty_list_validator(attribute, url_list)
    for list_element in url_list:
        url_validator(_, attribute, list_element)


def list_of_files_validator(_, attribute, file_list):
    """validate if a list has valid files"""
    if attribute.default is None and file_list is None:
        return
    is_non_empty_list_validator(attribute, file_list)
    for list_element in file_list:
        file_validator(_, attribute, list_element)


def list_of_dirs_validator(_, attribute, directory_list):
    """validate if a list has valid directories"""
    if attribute.default is None and directory_list is None:
        return
    is_non_empty_list_validator(attribute, directory_list)
    for directory_path in directory_list:
        directory_validator(_, attribute, directory_path)


def dict_with_keys_validator(_, __, value, expected_keys):
    """validate if a dict has keys"""
    missing_keys = set(expected_keys).difference(set(value))
    if missing_keys:
        raise InvalidConfigurationError(f"following keys are missing: {missing_keys}")

    unexpected_keys = set(value).difference(set(expected_keys))
    if unexpected_keys:
        raise InvalidConfigurationError(f"following keys are unknown: {unexpected_keys}")


def dict_structure_validator(_, __, value, reference_dict):
    """
    validate structure of a dictionary by checking:
    - if fields are optional or not
    - if fields have the correct types
    - if the validation of a nested config object is valid
    """
    unexpected_keys = set(value.keys()).difference(set(reference_dict.keys()))
    if unexpected_keys:
        raise InvalidConfigurationError(f"following keys are unknown: {unexpected_keys}")

    for key in reference_dict:
        if _is_optional_type(reference_dict[key]):
            _validate_optional_dict_keys(key, reference_dict, value)
        else:
            _validate_mandatory_dict_keys(key, reference_dict, value)


def _validate_mandatory_dict_keys(key, reference_dict, value):
    if key not in value.keys():
        raise InvalidConfigurationError(f"following key is missing: '{key}'")
    if hasattr(reference_dict[key], "__attrs_attrs__"):
        _ = reference_dict[key](**value[key])
    elif not isinstance(value[key], reference_dict[key]):
        raise InvalidConfigurationError(
            f"'{key}' has wrong type {type(value[key])}, expected {reference_dict[key]}."
        )


def _validate_optional_dict_keys(key, reference_dict, value):
    expected_type = _extract_not_none_type(reference_dict[key])
    if key in value.keys() and hasattr(expected_type, "__attrs_attrs__"):
        _ = expected_type(**value[key])
    elif key in value.keys() and not isinstance(value[key], expected_type):
        raise InvalidConfigurationError(
            f"'{key}' has wrong type {type(value[key])}, expected {reference_dict[key]}."
        )


def _extract_not_none_type(type_declaration):
    type_list = getattr(type_declaration, "__args__")
    return [typ for typ in type_list if not isinstance(typ, type(None))][0]


def _is_optional_type(given_type):
    """Checks if a given type is an optional type"""
    if hasattr(given_type, "__origin__"):
        if given_type.__origin__ is typing.Union:
            if type(None) in getattr(given_type, "__args__"):
                return True
    return False


def min_len_validator(_, attribute, value, min_length):
    """Temporary Validator to check for min length"""
    # TODO: This validator is available in attrs 22.1.0, currently semgrep depends on attrs 21.3,
    #  meaning this custom validator can be removed once the semgrep incompatibility is resolved
    #  (including the tests).
    if len(value) < min_length:
        raise ValueError(f"Length of '{attribute.name}' must be => {min_length}: {len(value)}")


def one_of_validator(_, attribute, value, member_list):
    """validates if the value contains one element of the given list"""
    contains = False
    for member in member_list:
        if member in value:
            contains = True
    if not contains:
        raise ValueError(f"{attribute.name} has to contain one of these members {member_list}")
