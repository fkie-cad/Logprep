"""module for json handling helper methods"""

import json


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
