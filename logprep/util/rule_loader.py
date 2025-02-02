"""module for rule loaders."""

import itertools
from pathlib import Path
from typing import Dict, List, Type

from logprep.abc.rule_loader import RuleLoader
from logprep.processor.base.rule import Rule
from logprep.util.defaults import RULE_FILE_EXTENSIONS
from logprep.util.getter import GetterFactory


class DirectoryRuleLoader(RuleLoader):
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

    def __init__(self, directory: str, rule_class: Type[Rule]):
        self.source = directory
        self.rule_class = rule_class

    @property
    def rules(self) -> List[Rule]:
        rule_files = (
            path.resolve()
            for path in Path(self.source).glob("**/*")
            if path.suffix in RULE_FILE_EXTENSIONS
        )
        rule_lists = (FileRuleLoader(str(file), self.rule_class).rules for file in rule_files)
        return list(itertools.chain(*rule_lists))


class FileRuleLoader(RuleLoader):
    """
    FileRuleLoader is responsible for loading rules from a file.
    The file can be located in a filesystem or in a remote location accessible
    via a HTTP.
    Parameters
    ----------
    file : str
      The path to the file containing the rules.
    Attributes
    ----------
    source : str
      The source file from which the rules are loaded.
    Methods
    -------
    rules
      Returns the list of rules loaded from the file.
    """

    def __init__(self, file: str, rule_class: Type[Rule]):
        self.rule_class = rule_class
        self.source = file

    @property
    def rules(self) -> List[Rule]:
        rules: List | Dict = []
        if self.source.endswith(".yaml") or self.source.endswith(".yml"):
            rules = GetterFactory.from_string(str(self.source)).get_yaml()
        elif self.source.endswith(".json"):
            rules = GetterFactory.from_string(str(self.source)).get_json()
        if isinstance(rules, dict):
            return DictRuleLoader(rules, self.rule_class).rules
        return ListRuleLoader(rules, self.rule_class).rules


class ListRuleLoader(RuleLoader):
    """
    ListRuleLoader is a class that loads rules from a list of dictionaries.
    Parameters
    ----------
    rules : list of dict
      A list of dictionaries where each dictionary represents a rule.
    Attributes
    ----------
    source : list of dict
      The source list of dictionaries containing the rules.
    Methods
    -------
    rules
      Returns a list of Rule objects created from the source list of dictionaries.
    """

    def __init__(self, rules: List[dict], rule_class: Type[Rule]):
        self.rule_class = rule_class
        self.source = rules

    @property
    def rules(self) -> List[Rule]:
        return [self.rule_class.create_from_dict(rule) for rule in self.source]


class DictRuleLoader(RuleLoader):
    """
    A rule loader that loads rules from a dictionary source.
    Parameters
    ----------
    source : dict
      A dictionary containing the rules to be loaded.
    Attributes
    ----------
    source : dict
      The source dictionary containing the rules.
    Methods
    -------
    rules
      Returns a list of rules created from the source dictionary.
    """

    def __init__(self, source: dict, rule_class: Type[Rule]):
        self.rule_class = rule_class
        self.source: dict = source

    @property
    def rules(self) -> List[Rule]:
        return [self.rule_class.create_from_dict(self.source)]
