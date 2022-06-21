""" validators to use with `attrs` fields"""
import os
from urllib.parse import urlparse

from logprep.processor.processor_factory_error import InvalidConfigurationError
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
