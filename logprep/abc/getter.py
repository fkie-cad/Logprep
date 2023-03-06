"""Module for getter interface"""
from abc import ABC, abstractmethod
import os
import re
from string import Template
import json
from typing import Dict, List, Union
from ruamel.yaml import YAML
from attrs import define, field, validators

yaml = YAML(typ="safe", pure=True)


@define(kw_only=True)
class Getter(ABC):
    """Abstract base class describing the getter interface and providing of a factory method."""

    class EnvTemplate(Template):
        """Template class for uppercase only template variables"""

        idpattern = r"(?a:[_A-Z][_A-Z0-9]*)"
        flags = re.VERBOSE

    protocol: str = field(validator=validators.instance_of(str))
    """Indicates the protocol for the factory to chose a matching getter."""
    target: str = field(validator=validators.instance_of(str))
    """The target which holds the content to return by get method."""

    missing_env_vars: list = field(
        validator=[
            validators.instance_of(list),
            validators.deep_iterable(member_validator=validators.instance_of(str)),
        ],
        factory=list,
    )
    """used variables in content but not set in environment"""

    def get(self) -> str:
        """calls the get_raw method, decodes the bytes to string and
        enriches by environment variables.
        """
        content = self.get_raw().decode("utf8")
        template = self.EnvTemplate(content)
        used_env_vars = self._get_used_env_vars(content, template)
        self.missing_env_vars = [env_var for env_var in used_env_vars if env_var not in os.environ]
        defaults_for_missing = {missing_key: "" for missing_key in self.missing_env_vars}
        return template.safe_substitute({**os.environ, **defaults_for_missing})

    def _get_used_env_vars(self, content, template):
        found_variables = template.pattern.findall(content)
        used_env_vars = map(lambda x: x[1], found_variables)
        used_braced_env_vars = map(lambda x: x[2], found_variables)
        return [
            var for var in {*used_env_vars, *used_braced_env_vars} if var
        ]  # deduplicate and clean out whitespace

    def get_yaml(self) -> Union[Dict, List]:
        """gets and parses the raw content to yaml"""
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
