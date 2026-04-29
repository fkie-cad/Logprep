"""Module for getter interface"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from string import Template
from typing import TypeAlias

from attrs import define, field, validators
from ruamel.yaml import YAML, YAMLError

logger = logging.getLogger("Getter")
yaml = YAML(typ="safe", pure=True)

BLOCKLIST_VARIABLE_NAMES = [
    "",
    " ",
    "LOGPREP_LIST",  # used by list_comparison processor
]

VALID_PREFIXES = ["LOGPREP_", "CI_", "GITHUB_", "PYTEST_"]

ContentType: TypeAlias = str


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
        """  # type: ignore[assignment]

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
        """Returns content with enriched environment variables."""
        raw, _ = self._get_raw()
        return self._resolve_content(raw)

    def _resolve_content(self, raw_content: bytes) -> str:
        content = raw_content.decode("utf8")
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

    def _resolve_content_by_content_type(self) -> dict | list | str:
        """Get content with enriched environment variables parsed based on content type."""

        raw, content_type = self._get_raw()
        content = self._resolve_content(raw)

        match content_type:
            case "application/json":
                return self._parse_json(content)
            case "application/yaml":
                return self._parse_yaml(content)
            case "text/plain" | None:
                return content
            case _:
                logger.warning("Unexpected content type.")
                return content

    @staticmethod
    def _parse_yaml(content: str) -> dict | list:
        """Parse yaml content to dict or json.

        Note: if parsed_yaml is empty, an empty dict will be returned."""

        parsed_yaml = list(yaml.load_all(content))
        if not parsed_yaml:
            return {}
        if len(parsed_yaml) > 1:
            return parsed_yaml
        return parsed_yaml.pop()

    def get_yaml(self) -> dict | list:
        """Gets and parses the raw content as yaml

        Content may already be parsed according to its actual content type,
        e.g. JSON content is returned as-is.
        """
        raw, _ = self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_yaml(content)

    @staticmethod
    def _parse_json(content: str) -> dict | list:
        """Parse content to json"""
        return json.loads(content)

    def get_json(self) -> dict | list:
        """Gets and parses the raw content as json
        Content may already be parsed according to its actual content type,
        e.g. YAML content is returned as-is.
        """
        raw, _ = self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_json(content)

    def get_collection(self) -> dict | list:
        """Gets and parses the raw content to yaml or json"""
        content = self._resolve_content_by_content_type()

        if isinstance(content, str):
            content = self._parse_yaml_or_json(content)

        return content

    def _parse_yaml_or_json(self, content: str) -> dict | list:
        """Helper which tries to parse content to list or dict"""
        try:
            return self._parse_yaml(content)
        except YAMLError:
            return self._parse_json(content)

    def get_dict(self) -> dict:
        """Gets dict and fails otherwise"""
        result = self.get_collection()
        if not isinstance(result, dict):
            raise ValueError("Value is not a dictionary")
        return result

    @staticmethod
    def _parse_newline_separated_list(content: str) -> list:
        """Helper which tries to convert content to list"""
        return content.splitlines()

    def get_list(self) -> list:
        """Gets list and fails otherwise"""

        content = self._resolve_content_by_content_type()

        if isinstance(content, str):
            content = self._parse_newline_separated_list(content)

        match content:
            case list():
                return content
            case _:
                raise ValueError("Content is not a list")

    def get_jsonl(self) -> list:
        """Gets and parses the raw content as jsonl"""
        parsed_events = []
        for json_string in self._parse_newline_separated_list(self.get()):
            if json_string.strip() != "":
                event = self._parse_json(json_string)
                parsed_events.append(event)
        return parsed_events

    @abstractmethod
    def _get_raw(self) -> tuple[bytes, ContentType | None]:
        """Get the content and content type of the raw content.

        Returns
        -------
        tuple[bytes, ContentType | None]
            The raw serialized content + content type.
        """

    def get_raw(self) -> bytes:
        """Get the raw content."""
        return self._get_raw()[0]
