import json

from yaml import safe_dump


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

    with open(config_path, "w") as generated_config_file:
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
    with open(jsonl_path, "r") as jsonl_file:
        for json_string in jsonl_file.readlines():
            if json_string.strip() != "":
                event = json.loads(json_string)
                parsed_events.append(event)
    return parsed_events


def parse_json(json_path):
    """
    Reads and parses one json file

    Parameters
    ----------
    json_path: str
        Path to the json file.

    Returns
    -------
    dict
        The dictionary representing the json.
    """
    with open(json_path, "r") as json_file:
        return json.load(json_file)
