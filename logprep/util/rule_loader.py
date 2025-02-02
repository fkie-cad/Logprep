"""module for rule loaders."""

from pathlib import Path
from typing import List

from logprep.abc.rule_loader import RuleLoader
from logprep.processor.base.rule import Rule
from logprep.util.getter import GetterFactory


class DirectoryRuleLoader(RuleLoader):

    def __init__(self, directory: Path):
        self.source = directory

    @property
    def rules(self) -> List[Rule]:
        return []


class FileRuleLoader(RuleLoader):
    """
    FileRuleLoader is responsible for loading rules from a file.
    The file can be located in a filesystem or in a remote location and
    accessible via a HTTP.
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

    def __init__(self, file: str):
        self.source = file

    @property
    def rules(self) -> List[Rule]:
        rules = GetterFactory.from_string(str(self.source)).get_yaml()
        if isinstance(rules, dict):
            return DictRuleLoader(rules).rules
        return ListRuleLoader(rules).rules


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

    def __init__(self, rules: List[dict]):
        self.source = rules

    @property
    def rules(self) -> List[Rule]:
        return [Rule._create_from_dict(rule) for rule in self.source]


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

    def __init__(self, source: dict):
        self.source: dict = source

    @property
    def rules(self) -> List[Rule]:
        return [Rule._create_from_dict(self.source)]
