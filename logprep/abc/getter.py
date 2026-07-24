"""Module for getter interface"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Iterable, TypeAlias

from attrs import define, field, validators
from ruamel.yaml import YAML, YAMLError

from logprep.util.environ import ENV_VARS, EnvTemplate

logger = logging.getLogger("Getter")
yaml = YAML(typ="safe", pure=True)


ContentType: TypeAlias = str


@define(kw_only=True)
class Getter(ABC):
    """Abstract base class describing the getter interface and providing of a factory method."""

    protocol: str = field(validator=validators.instance_of(str))
    """Indicates the protocol for the factory to chose a matching getter."""
    target: str = field(validator=validators.instance_of(str))
    """The target which holds the content to return by get method."""

    missing_env_vars: Iterable[str] = field(
        validator=[
            validators.instance_of((list, set)),
            validators.deep_iterable(member_validator=validators.instance_of(str)),
        ],
        factory=set,
        repr=False,
    )
    """used variables in content but not set in environment"""

    @property
    def uri(self) -> str:
        """Full-length URI of the getter target, including the protocol"""
        return f"{self.protocol}://{self.target}"

    def get(self) -> str:
        """Returns content with enriched environment variables."""
        raw, _ = self._get_raw()
        return self._resolve_content(raw)

    def _resolve_content(self, raw_content: bytes) -> str:
        content = raw_content.decode("utf8")
        template = EnvTemplate(content)
        resolved_content = template.safe_substitute(self._get_kwargs(template))
        logger.debug("resolved environment placeholders in content: %s", resolved_content)
        return resolved_content

    def _get_kwargs(self, template: EnvTemplate) -> dict[str, str]:
        used_env_vars = set(template.get_identifiers())
        self.missing_env_vars = used_env_vars.difference(ENV_VARS.keys())
        return ENV_VARS | {missing_key: "" for missing_key in self.missing_env_vars}

    def _resolve_content_by_content_type(self) -> dict | list | str:
        """Get content with enriched environment variables parsed based on content type."""

        raw, content_type = self._get_raw()
        # TODO make resolving env variables optional, especially for user-defined pure data payloads
        content = self._resolve_content(raw)

        match content_type:
            case "application/json":
                return self._parse_json(content)
            case "application/yaml":
                return self._parse_yaml(content)
            case "text/plain" | None:
                return content
            case _:
                logger.info("Unexpected content type: %s", content_type)
                return content

    @staticmethod
    def _parse_yaml(content: str) -> dict | list:
        """Parse yaml content to dict or json.

        Note: if parsed_yaml is empty, an empty dict will be returned."""

        try:
            parsed_yaml = list(yaml.load_all(content))
        except YAMLError:
            logger.debug("getter failed to deserialize yaml: %s", content, exc_info=True)
            raise
        if not parsed_yaml:
            return {}
        if len(parsed_yaml) > 1:
            return parsed_yaml
        return parsed_yaml.pop()

    def get_yaml(self) -> dict | list:
        """Gets and parses the raw content as yaml"""
        raw, _ = self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_yaml(content)

    @staticmethod
    def _parse_json(content: str) -> dict | list:
        """Parse content to json"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.debug("getter failed to deserialize json: %s", content, exc_info=True)
            raise

    def get_json(self) -> dict | list:
        """Gets and parses the raw content as json"""
        raw, _ = self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_json(content)

    def get_collection(self, content_field: str | None = None) -> dict | list:
        """Gets and parses the raw content to yaml or json"""
        content = self._resolve_content_by_content_type()

        content = Getter._apply_content_field(content, content_field)

        if isinstance(content, str):
            content = self._parse_yaml_or_json(content)

        return content

    def _parse_yaml_or_json(self, content: str) -> dict | list:
        """Helper which tries to parse content to list or dict"""
        try:
            return self._parse_yaml(content)
        except YAMLError:
            logger.debug("parsing yaml failed, falling back to json for content: %s", content)
            return self._parse_json(content)

    def get_dict(self) -> dict:
        """Gets dict and fails otherwise"""
        result = self.get_collection()
        if not isinstance(result, dict):
            raise ValueError(f"Expected a dict, got {type(result)}")
        return result

    @staticmethod
    def _parse_newline_separated_list(content: str) -> list:
        """Helper which tries to convert content to list"""
        return content.splitlines()

    @staticmethod
    def _apply_content_field(
        content: dict | list | str, content_field: str | None = None
    ) -> dict | list | str:
        if isinstance(content, dict) and content_field is not None:
            content = content[content_field]
        elif content_field is not None:
            raise ValueError(
                f"Expected mapping type when content_field is set, got {type(content)}"
            )

        return content

    def get_list(self, content_field: str | None = None) -> list:
        """Gets list and fails otherwise"""

        content = self._resolve_content_by_content_type()

        content = Getter._apply_content_field(content, content_field)

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
