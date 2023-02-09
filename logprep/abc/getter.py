"""Module for getter interface"""
from abc import ABC, abstractmethod
import os
from string import Template
import json
from typing import Dict, List, Union
from ruamel.yaml import YAML
from attrs import define, field, validators

pure_yaml = YAML(typ="safe", pure=True)
impure_yaml = YAML(typ="safe", pure=False)
base_yaml = YAML(typ="base", pure=False)


@define(kw_only=True)
class Getter(ABC):
    """Abstract base class describing the getter interface and providing of a factory method."""

    protocol: str = field(validator=validators.instance_of(str))
    """Indicates the protocol for the factory to chose a matching getter."""
    target: str = field(validator=validators.instance_of(str))
    """The target which holds the content to return by get method."""

    def get(self) -> str:
        """calls the get_raw method and returns the decoded content"""
        content = self.get_raw().decode("utf8")
        try:
            content = Template(content).substitute(**os.environ)
        except (KeyError, ValueError):
            pass
        return content

    def get_yaml(self) -> Union[Dict, List]:
        """gets and parses the raw content to yaml using only Python modules.

        Is slower but, has always expected behaviour.
        """
        return self._get_yaml_with_loader(pure_yaml)

    def get_impure_yaml(self) -> Union[Dict, List]:
        """gets and parses the raw content to yaml using non-Python modules if faster.

        Is faster, but may have different behaviour.
        """
        return self._get_yaml_with_loader(impure_yaml)

    def get_basic_yaml(self) -> Union[Dict, List]:
        """gets and parses the raw content to yaml into basic Python objects like lists and dicts.

        Has limited functionality, but is very fast.
        """
        return self._get_yaml_with_loader(base_yaml)

    def _get_yaml_with_loader(self, yaml: YAML) -> Union[Dict, List]:
        """gets and parses the raw content to yaml with the given YAML object."""
        raw = self.get()
        parsed_yaml = list(yaml.load_all(raw))
        if not parsed_yaml:
            return {}
        if len(parsed_yaml) > 1:
            return parsed_yaml
        return parsed_yaml.pop()

    def get_json(self) -> Union[Dict, List]:
        """gets and parses the raw content to json"""
        return json.loads(self.get())

    def get_jsonl(self) -> List:
        """gets and parses the raw content to jsonl"""
        parsed_events = []
        for json_string in self.get().splitlines():
            if json_string.strip() != "":
                event = json.loads(json_string)
                parsed_events.append(event)
        return parsed_events

    @abstractmethod
    def get_raw(self) -> bytearray:
        """Get the content.

        Returns
        -------
        str
            The raw serialized content.
        """
