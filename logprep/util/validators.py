""" validators to use with `attrs` fields"""
import os
from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.util.json_handling import is_json


def json_validator(_, __, value):
    """validate if a file is valid json"""
    if not is_json(value):
        raise InvalidConfigurationError(f"`{value}` is not valid json")


def file_validator(_, attribute, value):  # pylint: disable=no-self-use
    """validate if an attribute is a valid file"""
    if attribute.default is None and value is None:
        return
    if not isinstance(value, str):
        raise InvalidConfigurationError(f"{attribute.name} is not a str")
    if not os.path.exists(value):
        raise InvalidConfigurationError(f"{attribute.name} file '{value}' does not exist")
    if not os.path.isfile(value):
        raise InvalidConfigurationError(f"{attribute.name} '{value}' is not a file")


def list_of_files_validator(_, attribute, file_list):  # pylint: disable=no-self-use
    """validate if a list has valid files is a valid file"""
    if attribute.default is None and file_list is None:
        return
    if not isinstance(file_list, list):
        raise InvalidConfigurationError(f"{attribute.name} is not a list")
    if len(file_list) == 0:
        raise InvalidConfigurationError(f"{attribute.name} is empty list")
    for list_element in file_list:
        file_validator(_, attribute, list_element)


def list_of_dirs_validator(_, attribute, directory_list):  # pylint: disable=no-self-use
    """validate if a list has valid directories"""
    if attribute.default is None and directory_list is None:
        return
    if not isinstance(directory_list, list):
        raise InvalidConfigurationError(f"{attribute.name} is not a list")
    if len(directory_list) == 0:
        raise InvalidConfigurationError(f"{attribute.name} is empty list")
    for directory_path in directory_list:
        if not os.path.exists(directory_path):
            raise InvalidConfigurationError(f"'{directory_path}' does not exist")
        if not os.path.isdir(directory_path):
            raise InvalidConfigurationError(f"'{directory_path}' is not a directory")
