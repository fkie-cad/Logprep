"""Module for getter interface"""

# TODO(async-followup): Remove mypy ignore after completing the async migration.
# mypy: disable-error-code="override"

from abc import ABC, abstractmethod

from attrs import define

from logprep.abc.getter import ContentType
from logprep.util.getter import Getter as NonNGGetter
from logprep.util.getter import logger


@define(kw_only=True)
class Getter(NonNGGetter, ABC):
    """Abstract base class describing the ng getter interface and providing of a factory method."""

    async def get(self) -> str:
        """Returns content with enriched environment variables."""
        raw, _ = await self._get_raw()
        return self._resolve_content(raw)

    async def _resolve_content_by_content_type(self) -> dict | list | str:
        """Get content with enriched environment variables parsed based on content type."""

        raw, content_type = await self._get_raw()
        # TODO make resolving env variables optional, especially for user-defined pure data payloads
        content = self._resolve_content(raw)

        match content_type:
            case "application/json":
                return self._parse_json(content)
            case "application/yaml" | "text/yaml":
                return self._parse_yaml(content)
            case "text/plain" | None:
                return content
            case _:
                logger.info("Unexpected content type: %s", content_type)
                return content

    async def get_yaml(self) -> dict | list:
        """Gets and parses the raw content as yaml"""
        raw, _ = await self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_yaml(content)

    async def get_json(self) -> dict | list:
        """Gets and parses the raw content as json"""
        raw, _ = await self._get_raw()
        content = self._resolve_content(raw)
        return self._parse_json(content)

    async def get_collection(self, content_field: str | None = None) -> dict | list:
        """Gets and parses the raw content to yaml or json"""
        content = await self._resolve_content_by_content_type()

        if isinstance(content, str):
            content = self._parse_yaml_or_json(content)

        content = Getter._apply_content_field(content, content_field)
        if isinstance(content, str):
            content = self._parse_yaml_or_json(content)

        return content

    async def get_dict(self, content_field: str | None = None) -> dict:
        """Gets dict and fails otherwise"""
        result = await self.get_collection(content_field=content_field)
        if not isinstance(result, dict):
            raise ValueError(f"Expected a dict, got {type(result)}")
        return result

    async def get_list(self, content_field: str | None = None) -> list:
        """Gets list and fails otherwise"""
        content = await self._resolve_content_by_content_type()
        if content_field is not None and isinstance(content, str):
            content = self._parse_yaml_or_json(content)

        content = Getter._apply_content_field(content, content_field)

        if isinstance(content, str):
            content = self._parse_newline_separated_list(content)

        match content:
            case list():
                return content
            case _:
                raise ValueError("Content is not a list")

    async def get_jsonl(self) -> list:
        """Gets and parses the raw content as jsonl"""
        parsed_events = []
        for json_string in self._parse_newline_separated_list(await self.get()):
            if json_string.strip() != "":
                event = self._parse_json(json_string)
                parsed_events.append(event)
        return parsed_events

    @abstractmethod
    async def _get_raw(self) -> tuple[bytes, ContentType | None]:
        """Get the content and content type of the raw content.

        Returns
        -------
        tuple[bytes, ContentType | None]
            The raw serialized content + content type.
        """

    async def get_raw(self) -> bytes:
        """Get the raw content."""
        return (await self._get_raw())[0]
