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
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        custom_patterns_dir: "http://the.patterns.us/patterns.zip"

.. autoclass:: logprep.processor.grokker.processor.Grokker.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.grokker.rule
"""

import re
from pathlib import Path
from zipfile import ZipFile

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingError,
    ProcessingWarning,
)
from logprep.processor.grokker.rule import GrokkerRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import add_field_to, get_dotted_field_value


class Grokker(Processor):
    """A processor that dissects a message by grok patterns"""

    rule_class = GrokkerRule

    _config: "Grokker.Config"

    @define(kw_only=True)
    class Config(Processor.Config):
        """Config of Grokker"""

        custom_patterns_dir: str = field(default="", validator=validators.instance_of(str))
        """(Optional) A directory or URI to load patterns from. All files in all subdirectories
        will be loaded recursively. If an uri is given, the target file has to be a zip file with a
        directory structure in it.
        """

    def _apply_rules(self, event: dict, rule: GrokkerRule):
        conflicting_fields = []
        matches = []
        for dotted_field, grok in rule.actions.items():
            field_value = get_dotted_field_value(event, dotted_field)
            if field_value is None:
                if rule.ignore_missing_fields:
                    continue
                error = BaseException(f"{self.name}: missing source_field: '{dotted_field}'")
                self._handle_warning_error(event=event, rule=rule, error=error)
                continue
            try:
                result = grok.match(field_value)
            except TimeoutError as error:
                raise ProcessingError(
                    self,
                    f"Grok pattern timeout for source field: '{dotted_field}' in rule '{rule}', "
                    f"the grok pattern might be too complex.",
                ) from error
            if result is None or result == {}:
                continue
            matches.append(True)
            for dotted_field, value in result.items():
                if value is None:
                    continue
                success = add_field_to(
                    event, dotted_field, value, rule.extend_target_list, rule.overwrite_target
                )
                if not success:
                    conflicting_fields.append(dotted_field)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)
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
            self._logger.debug("start grok pattern download...")
            archive = Path(f"{target_dir}.zip")
            archive.touch()
            archive.write_bytes(GetterFactory.from_string(source_file).get_raw())
            self._logger.debug("finished grok pattern download.")
            with ZipFile(str(archive), mode="r") as zip_file:
                zip_file.extractall(target_dir)
