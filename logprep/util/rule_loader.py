"""module for rule loaders."""

import itertools
from pathlib import Path
from typing import Dict, List

from logprep.processor.base.rule import Rule
from logprep.util.defaults import RULE_FILE_EXTENSIONS
from logprep.util.getter import GetterFactory


class RuleLoader:
    """A class to load rules from various sources such as dictionaries,
    file paths, or lists of these.

    Parameters:
    -----------
    source : list of dict or str or dict or str
      A list of dictionaries, file paths, a single dictionary,
      or a single file path containing the rules to be loaded.

    processor_name : str
      The name of the processor that the rules belong to.

    Attributes
    ----------
    source : list of dict or str or dict or str
      The source from which the rules are to be loaded.

    Methods
    -------
    rules:
      Load rules from the specified source and return a list of Rule objects.
    """

    def __init__(self, source: List[Dict | str] | Dict | str, processor_name: str):
        self.source = source
        self.processor_name = processor_name

    @property
    def rules(self) -> List[Rule]:
        """
        Load rules from a list of dictionaries, dicts or file paths.
        Parameters
        ----------
        rules : list of dict or str
          A list of dictionaries or file paths containing the rules to be loaded.
        processor_name : str
          The name of the processor that the rules belong to.
        Returns
        -------
        list of Rule
          A list of Rule objects created from the source list of dictionaries or files.
        """
        rules: List[Rule] = []
        match self.source:
            case dict():
                rules.extend(DictRuleLoader(self.source, self.processor_name).rules)
            case str():
                path = Path(self.source)
                if path.is_dir():
                    rules.extend(DirectoryRuleLoader(self.source, self.processor_name).rules)
                if path.is_file():
                    rules.extend(FileRuleLoader(self.source, self.processor_name).rules)
            case list():
                for element in self.source:
                    rules.extend(RuleLoader(element, self.processor_name).rules)
        return rules


class DirectoryRuleLoader:
    """
    DirectoryRuleLoader is responsible for loading rules from a directory recursively.
    The directory can contain multiple rule files with supported extensions.
    In every rule file, multiple rules can be defined.
    Supported extensions are defined in the RULE_FILE_EXTENSIONS constant.

    Parameters
    ----------
    directory : str
      The path to the directory containing the rule files.
    Attributes
    ----------
    source : str
      The source directory from which the rule files are loaded.
    Methods
    -------
    rules
      Returns the list of rules loaded from the directory.
    """

    def __init__(self, source: str, processor_name: str):
        self.source = source
        self.processor_name = processor_name

    @property
    def rules(self) -> List[Rule]:
        rule_files = (
            path.resolve()
            for path in Path(self.source).glob("**/*")
            if path.suffix in RULE_FILE_EXTENSIONS
        )
        rule_lists = (FileRuleLoader(str(file), self.processor_name).rules for file in rule_files)
        return list(itertools.chain(*rule_lists))


class FileRuleLoader(RuleLoader):
    @property
    def rules(self) -> List[Rule]:
        rule_definitions: List | Dict = []
        if self.source.endswith(".yaml") or self.source.endswith(".yml"):
            rule_definitions = GetterFactory.from_string(str(self.source)).get_yaml()
        elif self.source.endswith(".json"):
            rule_definitions = GetterFactory.from_string(str(self.source)).get_json()
        if not rule_definitions:
            return []
        if isinstance(rule_definitions, dict):
            return DictRuleLoader(rule_definitions, self.processor_name).rules
        if isinstance(rule_definitions, list):
            rules = []
            for rule in rule_definitions:
                rules.extend(DictRuleLoader(rule, self.processor_name).rules)
            return rules
        return []


class DictRuleLoader(RuleLoader):
    @property
    def rules(self) -> List[Rule]:

        from logprep.registry import Registry  # pylint: disable=import-outside-toplevel

        rule_class = Registry.get_rule_class_by_rule_definition(self.source)
        return [rule_class.create_from_dict(self.source, self.processor_name)]
