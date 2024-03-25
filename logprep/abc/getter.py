"""Module for getter interface"""

import json
import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from string import Template
from typing import Dict, List, Union

from attrs import define, field, validators
from ruamel.yaml import YAML

yaml = YAML(typ="safe", pure=True)

BLOCKLIST_VARIABLE_NAMES = [
    "",
    " ",
    "LOGPREP_LIST",  # used by list_comparison processor
]

VALID_PREFIXES = ["LOGPREP_", "CI_", "GITHUB_", "PYTEST_"]


@define(kw_only=True)
class Getter(ABC):
    """Abstract base class describing the getter interface and providing of a factory method."""

    class EnvTemplate(Template):
        """Template class for uppercase only template variables"""

        pattern = r"""
        \$(?:
            (?P<escaped>\$\$\$)|
            (?P<named>(?!LOGPREP_LIST)(?=LOGPREP_|CI_|GITHUB_|PYTEST_)[_A-Z0-9]*)|
            {(?P<braced>(?!LOGPREP_LIST)(?=LOGPREP_|CI_|GITHUB_|PYTEST_)[_A-Z0-9]*)}|
            (?P<invalid>)
        )
        """
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
        repr=False,
    )
    """used variables in content but not set in environment"""

    def get(self) -> str:
        """calls the get_raw method, decodes the bytes to string and
        enriches by environment variables.
        """
        content = self.get_raw().decode("utf8")
        template = self.EnvTemplate(content)
        kwargs = self._get_kwargs(template, content)
        return template.safe_substitute(**kwargs)

    def _get_kwargs(self, template, content):
        used_env_vars = list(self._get_used_env_vars(content, template))
        self.missing_env_vars = [env_var for env_var in used_env_vars if env_var not in os.environ]
        defaults_for_missing = {missing_key: "" for missing_key in self.missing_env_vars}
        kwargs = deepcopy(os.environ)
        kwargs |= defaults_for_missing
        return kwargs

    def _get_used_env_vars(self, content, template):
        found_variables = template.pattern.findall(
            content
        )  # returns a list of tuples in form (escaped, named, braced, invalid)
        used_named_env_vars = map(lambda x: x[1], found_variables)
        used_braced_env_vars = map(lambda x: x[2], found_variables)
        return (item for item in {*used_named_env_vars, *used_braced_env_vars} if item)

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
