"""module for rule loaders."""

import itertools
from pathlib import Path
from typing import Dict, Generator, List

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

    @property
    def rule_definitions(self) -> List[Dict]:
        rule_definitions: List[Dict] = []
        match self.source:
            case dict():
                rule_definitions.append(self.source)
            case str():
                path = Path(self.source)
                if path.is_dir():
                    rule_definitions.extend(
                        DirectoryRuleLoader(self.source, self.processor_name).rule_definitions
                    )
                else:
                    rule_definitions.extend(
                        FileRuleLoader(self.source, self.processor_name).rule_definitions
                    )
            case list():
                for element in self.source:
                    rule_definitions.extend(
                        RuleLoader(element, self.processor_name).rule_definitions
                    )
        return rule_definitions


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
        rule_files = self.get_rule_files(self.source)
        rule_lists = (FileRuleLoader(str(file), self.processor_name).rules for file in rule_files)
        return list(itertools.chain(*rule_lists))

    @property
    def rule_definitions(self) -> List[Dict]:
        rule_files = self.get_rule_files(self.source)
        rule_definitions = (
            FileRuleLoader(str(file), self.processor_name).rule_definitions for file in rule_files
        )
        return list(itertools.chain(*rule_definitions))

    @staticmethod
    def get_rule_files(source: str) -> Generator[str, None, None]:
        """return a list of rule files in the source directory."""
        return (
            str(path.resolve())
            for path in Path(source).glob("**/*")
            if path.suffix in RULE_FILE_EXTENSIONS
        )


class FileRuleLoader(RuleLoader):
    @property
    def rules(self) -> List[Rule]:
        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")
        return list(
            itertools.chain(
                *[
                    DictRuleLoader(rule_definition, self.processor_name).rules
                    for rule_definition in self.rule_definitions
                ]
            )
        )

    @property
    def rule_definitions(self) -> List[Dict]:
        rule_definitions: List[Dict] | Dict = []
        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")
        if self.source.endswith(".yaml") or self.source.endswith(".yml"):
            rule_definitions = GetterFactory.from_string(self.source).get_yaml()
        elif self.source.endswith(".json"):
            rule_definitions = GetterFactory.from_string(self.source).get_json()
        if not isinstance(rule_definitions, list):
            rule_definitions = [rule_definitions]
        return rule_definitions


class DictRuleLoader(RuleLoader):
    @property
    def rules(self) -> List[Rule]:

        from logprep.registry import Registry  # pylint: disable=import-outside-toplevel

        if not isinstance(self.source, dict):
            raise TypeError(f"Expected a dictionary, got {type(self.source)}")
        rule_class = Registry.get_rule_class_by_rule_definition(self.source)
        return [rule_class.create_from_dict(self.source, self.processor_name)]
