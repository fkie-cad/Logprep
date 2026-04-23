"""Module for getter interface"""

import json
import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from string import Template
from typing import TypeAlias

from attrs import define, field, validators
from ruamel.yaml import YAML, YAMLError

yaml = YAML(typ="safe", pure=True)

BLOCKLIST_VARIABLE_NAMES = [
    "",
    " ",
    "LOGPREP_LIST",  # used by list_comparison processor
]

VALID_PREFIXES = ["LOGPREP_", "CI_", "GITHUB_", "PYTEST_"]

# TODO: get config informations for related processor
CONTENT_FIELD: None | str = None
"""If the resolved content is a mapping, use this field name to extract the actual content."""

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

    def get(self) -> dict | list | str:
        """Returns content with enriched environment variables."""
        content = self._get_parsed_content()
        return content

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

    def _get_parsed_content(self) -> dict | list | str:
        """Get content with enriched environment variables parsed based on content type."""

        raw, content_type = self._get_raw()
        content = self._resolve_content(raw)

        match content_type:
            case "application/json":
                if isinstance(content, dict | list):
                    return content

                json_content: dict | list = self._to_json(content)

                if isinstance(json_content, dict) and CONTENT_FIELD is not None:
                    if CONTENT_FIELD in json_content:
                        json_content = json_content[CONTENT_FIELD]
                    else:
                        raise ValueError(f"Field '{CONTENT_FIELD}' not found in content.")

                return json_content
            case "application/yaml":
                if isinstance(content, dict | list):
                    return content

                yaml_content: dict | list = self._to_yaml(content)

                if isinstance(yaml_content, dict) and CONTENT_FIELD is not None:
                    if CONTENT_FIELD in yaml_content:
                        yaml_content = yaml_content[CONTENT_FIELD]
                    else:
                        raise ValueError(f"Field '{CONTENT_FIELD}' not found in content.")

                return yaml_content
            case "text/plain":
                if isinstance(content, str):
                    return content
                raise ValueError(
                    f"Content type '{content_type}' does not match with parsed content"
                )
            case _:
                if isinstance(content, str):
                    return content
                raise ValueError(
                    f"Content type not set. Expecting a simple str (decoded raw content from bytes)"
                )

    @staticmethod
    def _to_yaml(content: str) -> dict | list:
        """Converts content to json"""
        parsed_yaml = list(yaml.load_all(content))
        if not parsed_yaml:
            return {}
        if len(parsed_yaml) > 1:
            return parsed_yaml
        return parsed_yaml.pop()

    def get_yaml(self) -> dict | list:
        """Gets and parses the raw content to yaml"""
        content = self._get_parsed_content()

        if isinstance(content, dict | list):
            return content

        return self._to_yaml(content)

    @staticmethod
    def _to_json(content: str) -> dict | list:
        """Converts content to json"""
        return json.loads(content)

    def get_json(self) -> dict | list:
        """Gets and parses the raw content to json"""
        content = self._get_parsed_content()

        if isinstance(content, dict | list):
            return content

        return self._to_json(content)

    def get_collection(self) -> dict | list:
        """Gets and parses the raw content to yaml or json if yaml fails"""
        content = self._get_parsed_content()

        if isinstance(content, str):
            # handles unknown content_type or text/plain
            content = self._try_parse(content)

        return content

    def _try_parse(self, content: str) -> dict | list:
        """Helper which tries to convert content to list or dict"""
        try:
            return self._to_yaml(content)
        except YAMLError:
            return self._to_json(content)

    def get_dict(self) -> dict:
        """Gets dict and fails otherwise"""
        result = self.get_collection()
        if not isinstance(result, dict):
            raise ValueError("Value is not a dictionary")
        return result

    @staticmethod
    def _to_list(content: str) -> list:
        """Helper which tries to convert content to list"""
        return content.splitlines()

    def get_list(self) -> list:
        """Gets list and fails otherwise"""

        content = self._get_parsed_content()

        if isinstance(content, str):
            content = self._try_parse(content)

        match content:
            case dict():
                any_content = content.get(CONTENT_FIELD)

                if isinstance(any_content, list):
                    content = any_content
                elif isinstance(any_content, str):
                    content = self._try_parse(any_content)

                if isinstance(content, list):
                    return content

                raise ValueError("Content is not a list")
            case list():
                return content
            case _:
                raise ValueError("Content has invalid type")

    def get_jsonl(self) -> list[dict | list]:
        """Gets and parses the raw content to jsonl"""
        parsed_events = []
        content = self._get_parsed_content()

        if isinstance(content, str):
            for content in self._to_list(content):
                if content.strip() != "":
                    event = self._to_json(content)
                    parsed_events.append(event)
        elif isinstance(content, list | dict):
            parsed_events.append(content)

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
        """Get the content.

        Returns
        -------
        str
            The raw serialized content.
        """

        return self._get_raw()[0]
