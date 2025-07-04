"""
Grokker
=======

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

import logging
import re
from pathlib import Path
from zipfile import ZipFile

from attrs import define, field, validators

from logprep.processor.base.exceptions import ProcessingError, ProcessingWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.grokker.rule import GrokkerRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import add_fields_to, get_dotted_field_value

logger = logging.getLogger("Grokker")


class Grokker(FieldManager):
    """A processor that dissects a message by grok patterns"""

    rule_class = GrokkerRule

    _config: "Grokker.Config"

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """Config of Grokker"""

        custom_patterns_dir: str = field(default="", validator=validators.instance_of(str))
        """(Optional) A directory or URI to load patterns from. All files in all subdirectories
        will be loaded recursively. If an uri is given, the target file has to be a zip file with a
        directory structure in it.
        """

    def _apply_rules(self, event: dict, rule: GrokkerRule):
        matches = []
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
            if result is None or result == {}:
                continue
            matches.append(True)
            add_fields_to(
                event,
                result,
                rule=rule,
                merge_with_target=rule.merge_with_target,
                overwrite_target=rule.overwrite_target,
            )
        if self._handle_missing_fields(event, rule, rule.actions.keys(), source_values):
            return
        if not matches:
            raise ProcessingWarning("no grok pattern matched", rule, event)

    def setup(self):
        """Loads the action mapping. Has to be called before processing"""
        super().setup()
        custom_patterns_dir = self._config.custom_patterns_dir
        if re.search(r"http(s)?:\/\/.*?\.zip", custom_patterns_dir):
            patterns_tmp_path = Path("/tmp/grok_patterns")
            self._download_zip_file(source_file=custom_patterns_dir, target_dir=patterns_tmp_path)
            for rule in self.rules:
                rule.set_mapping_actions(patterns_tmp_path)
            return
        if custom_patterns_dir:
            for rule in self.rules:
                rule.set_mapping_actions(custom_patterns_dir)
            return
        for rule in self.rules:
            rule.set_mapping_actions()

    def _download_zip_file(self, source_file: str, target_dir: Path):
        if not target_dir.exists():
            logger.debug("start grok pattern download...")
            archive = Path(f"{target_dir}.zip")
            archive.touch()
            archive.write_bytes(GetterFactory.from_string(source_file).get_raw())
            logger.debug("finished grok pattern download.")
            with ZipFile(str(archive), mode="r") as zip_file:
                zip_file.extractall(target_dir)
