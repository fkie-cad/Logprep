""" module for json handling helper methods"""
import json
import os
from typing import List

from yaml import safe_dump


def list_json_files_in_directory(directory: str) -> List[str]:
    """
    Collects all json and yaml files from a given directory and it's subdirectories.

    Parameters
    ----------
    directory: str
        Path to a directory which should be scanned

    Returns
    -------
    List[str]
        List of filenames in the given directory
    """
    valid_file_paths = []
    for root, _, files in os.walk(directory):
        for file_name in [
            file
            for file in files
            if (
                (file.endswith(".json") or file.endswith(".yml"))
                and not file.endswith("_test.json")
            )
        ]:
            valid_file_paths.append(os.path.join(root, file_name))
    return valid_file_paths


def dump_config_as_file(config_path, config):
    """
    Saves a config file based on the given config dictionary.

    Parameters
    ----------
    config_path: str
        The path were the File should be saved
    config: dict
        The configuration that should be saved
    """

    with open(config_path, "w", encoding="utf8") as generated_config_file:
        safe_dump(config, generated_config_file)


def parse_jsonl(jsonl_path):
    """
    Read and parse all json events from a given jsonl file.

    Parameters
    ----------
    jsonl_path: str
        Path to the jsonl file that contains all the events.

    Returns
    -------
    list[dict]
        A list of dictionaries where each dictionary represents one event
    """
    parsed_events = []
    with open(jsonl_path, "r", encoding="utf8") as jsonl_file:
        for json_string in jsonl_file.readlines():
            if json_string.strip() != "":
                event = json.loads(json_string)
                parsed_events.append(event)
    return parsed_events


def parse_json(json_path):
    """
    Reads and parses one json file and return it as list, containing either only one json or
    multiple jsons depending on the file.

    Parameters
    ----------
    json_path: str
        Path to the json file.

    Returns
    -------
    list
        A list of dictionaries representing the json/jsons.
    """
    with open(json_path, "r", encoding="utf8") as json_file:
        parsed_json = json.load(json_file)
        if isinstance(parsed_json, dict):
            parsed_json = [parsed_json]
        return parsed_json


def is_json(path):
    """Tests if a filehandle returns valid json"""
    with open(path, "r", encoding="utf8") as json_file:
        try:
            json.load(json_file)
        except ValueError:
            return False
        return True
