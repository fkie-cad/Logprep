"""
|PROCESSOR_NAME|
================

The `grokker` processor dissects a message on a basis of grok patterns. This processor is based
of the ideas of the logstash grok filter plugin.
(see: https://www.elastic.co/guide/en/logstash/current/plugins-filters-grok.html)

The default builtin grok patterns shipped with logprep are the same than in logstash.


Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - my_grokker:
        type: grokker
        rules:
            - tests/testdata/rules/rules
        custom_patterns_dir: "http://the.patterns.us/patterns.zip"

.. autoclass:: logprep.processor.grokker.processor.Grokker.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.grokker.rule
"""

import asyncio
import logging
import re
import tempfile
import typing
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from zipfile import ZipFile

from attrs import define, field, validators

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.exceptions import ProcessingError, ProcessingWarning
from logprep.processor.base.rule import Rule
from logprep.processor.grokker.rule import GrokkerRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import FieldValue, add_fields_to, get_dotted_field_value

logger = logging.getLogger("Grokker")


@asynccontextmanager
async def _temporary_directory(*, suffix: str = "") -> AsyncIterator[Path]:
    """Create and clean up a temporary directory without blocking the event loop."""
    temporary_directory = await asyncio.to_thread(
        tempfile.TemporaryDirectory,
        suffix=suffix,
    )

    try:
        yield Path(temporary_directory.name)
    finally:
        await asyncio.to_thread(temporary_directory.cleanup)


class Grokker(FieldManager):
    """A processor that dissects a message by grok patterns"""

    rule_class = GrokkerRule  # type: ignore
    # TBD, inheritance hierarchy needs to be refactored

    _config: "Grokker.Config"

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config of Grokker"""

        custom_patterns_dir: str = field(default="", validator=validators.instance_of(str))
        """(Optional) A directory or URI to load patterns from. All files in all subdirectories
        will be loaded recursively. If an uri is given, the target file has to be a zip file with a
        directory structure in it.
        """

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(Grokker.Config, self._config)

    @property
    def rules(self) -> Sequence[GrokkerRule]:
        """Returns all rules"""
        return typing.cast(Sequence[GrokkerRule], super().rules)

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        """Apply the configured grok patterns to an event"""
        rule = typing.cast(GrokkerRule, rule)
        any_match = False
        source_values = []
        for dotted_field, grok in rule.actions.items():
            field_value = get_dotted_field_value(event, dotted_field)
            source_values.append(field_value)
            if field_value is None:
                continue
            try:
                result = grok.match(field_value)
            except TimeoutError as error:
                self._handle_missing_fields(event, rule, rule.actions.keys(), source_values)
                raise ProcessingError(
                    f"Grok pattern timeout for source field: '{dotted_field}' in rule '{rule}', "
                    f"the grok pattern might be too complex.",
                    rule,
                ) from error
            if result is None:
                continue
            any_match = True
            if result == {}:
                continue
            add_fields_to(
                event,
                result,
                rule=rule,
                merge_with_target=rule.merge_with_target,
                overwrite_target=rule.overwrite_target,
            )
        if self._handle_missing_fields(event, rule, rule.actions.keys(), source_values):
            return
        if not any_match:
            raise ProcessingWarning("no grok pattern matched", rule, event)

    async def setup(self) -> None:
        """Loads the action mapping. Has to be called before processing"""
        await super().setup()

        custom_patterns_dir = self.config.custom_patterns_dir

        if re.search(r"http(s)?:\/\/.*?\.zip", custom_patterns_dir):
            async with _temporary_directory(suffix="grok") as patterns_tmp_path:
                await self._download_zip_file(
                    source_file=custom_patterns_dir,
                    target_dir=patterns_tmp_path,
                )

                for rule in self.rules:
                    await asyncio.to_thread(
                        rule.set_mapping_actions,
                        str(patterns_tmp_path),
                    )
            return

        if custom_patterns_dir:
            for rule in self.rules:
                await asyncio.to_thread(
                    rule.set_mapping_actions,
                    str(custom_patterns_dir),
                )
            return

        for rule in self.rules:
            await asyncio.to_thread(rule.set_mapping_actions)

    async def _download_zip_file(self, source_file: str, target_dir: Path):
        """Download and extract a ZIP archive containing custom grok patterns"""
        logger.debug("start grok pattern download...")

        getter = GetterFactory.from_string(source_file)

        # TODO: await get_raw() once the getter supports async operations.
        archive_content = await asyncio.to_thread(getter.get_raw)

        logger.debug("finished grok pattern download.")

        await asyncio.to_thread(
            self._extract_zip_file,
            archive_content,
            target_dir,
        )

    @staticmethod
    def _extract_zip_file(archive_content: bytes, target_dir: Path) -> None:
        """Extract ZIP archive content into the target directory"""
        with tempfile.TemporaryFile("wb+") as archive:
            archive.write(archive_content)
            archive.seek(0)

            with ZipFile(archive, mode="r") as zip_file:
                zip_file.extractall(target_dir)
