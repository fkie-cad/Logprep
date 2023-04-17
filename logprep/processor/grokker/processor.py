"""
Grokker
============

The `grokker` processor ...


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: grokker
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
import re
from pathlib import Path
from zipfile import ZipFile

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.processor.grokker.rule import GrokkerRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import add_field_to, get_dotted_field_value


class Grokker(Processor):
    """A processor that ..."""

    rule_class = GrokkerRule

    _config: "Grokker.Config"

    @define(kw_only=True)
    class Config(Processor.Config):
        """Config of Grokker"""

        custom_patterns_dir: str = field(default="", validator=validators.instance_of(str))
        """(Optional) A directory to load patterns from. All files in all subdirectories will be loaded
        recursively. 
        """

    def _apply_rules(self, event: dict, rule: GrokkerRule):
        conflicting_fields = []
        matches = []
        for dotted_field, grok in rule.actions.items():
            field_value = get_dotted_field_value(event, dotted_field)
            result = grok.match(field_value)
            if result is None:
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
            raise FieldExistsWarning(self, rule, event, conflicting_fields)
        if not matches:
            raise ProcessingWarning(self, "no grok pattern matched", rule, event)

    def setup(self):
        """Loads the action mapping. Has to be called before processing"""
        super().setup()
        if custom_patterns_dir := self._config.custom_patterns_dir:
            if re.search(r"http:\/\/.*?\.zip", custom_patterns_dir):
                patterns_tmp_path = Path("/tmp/grok_patterns")
                if not patterns_tmp_path.exists():
                    self._logger.debug("start grok pattern download...")
                    archive = Path(f"{patterns_tmp_path}.zip")
                    archive.touch()
                    archive.write_bytes(GetterFactory.from_string(custom_patterns_dir).get_raw())
                    self._logger.debug("finished grok pattern download.")
                    with ZipFile(str(archive), mode="r") as zip_file:
                        zip_file.extractall(patterns_tmp_path)
                self._load_patterns(patterns_tmp_path)
            else:
                self._load_patterns(custom_patterns_dir)

    def _load_patterns(self, custom_patterns_dir):
        for rule in self.rules:
            rule.set_mapping_actions(custom_patterns_dir)
