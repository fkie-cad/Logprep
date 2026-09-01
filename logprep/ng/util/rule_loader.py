"""module for rule loaders."""

import asyncio
import itertools
from logging import getLogger
from pathlib import Path
from typing import Iterable, Sequence

from logprep.ng.util.getter import GetterFactory
from logprep.processor.base.rule import Rule
from logprep.util.defaults import RULE_FILE_EXTENSIONS

logger = getLogger("RuleLoader")


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
    """

    def __init__(self, source: Sequence[dict | str] | dict | str, processor_name: str):
        self.source = source
        self.processor_name = processor_name

    async def load_rules(self) -> list[Rule]:
        """
        Load rules from a list of dictionaries, dicts or file paths asynchronously.

        Returns
        -------
        list of Rule
          A list of Rule objects created from the source list of dictionaries or files.
        """
        rules: list[Rule] = []

        match self.source:
            case dict():
                rules.extend(await DictRuleLoader(self.source, self.processor_name).load_rules())
            case str():
                path = Path(self.source)

                if await asyncio.to_thread(path.is_dir):
                    rules.extend(
                        await DirectoryRuleLoader(
                            self.source,
                            self.processor_name,
                        ).load_rules()
                    )

                if await asyncio.to_thread(path.is_file):
                    rules.extend(
                        await FileRuleLoader(
                            self.source,
                            self.processor_name,
                        ).load_rules()
                    )
            case list():
                for element in self.source:
                    rules.extend(
                        await RuleLoader(
                            element,
                            self.processor_name,
                        ).load_rules()
                    )

        return rules

    async def load_rule_definitions(self) -> list[dict]:
        """
        Load rule definitions from a list of directories, dicts or file paths asynchronously.

        Returns
        -------
        list of dict
          A list of rule definitions.
        """
        rule_definitions: list[dict] = []

        match self.source:
            case dict():
                rule_definitions.append(self.source)
            case str():
                path = Path(self.source)

                if await asyncio.to_thread(path.is_dir):
                    rule_definitions.extend(
                        await DirectoryRuleLoader(
                            self.source,
                            self.processor_name,
                        ).load_rule_definitions()
                    )
                else:
                    rule_definitions.extend(
                        await FileRuleLoader(
                            self.source,
                            self.processor_name,
                        ).load_rule_definitions()
                    )
            case list():
                for element in self.source:
                    rule_definitions.extend(
                        await RuleLoader(
                            element,
                            self.processor_name,
                        ).load_rule_definitions()
                    )

        return rule_definitions

    @staticmethod
    async def files_by_extensions(
        source: str,
        extensions: Iterable | None = None,
    ) -> list[str]:
        """return a list of rule files in the source directory"""
        if extensions is None:
            extensions = RULE_FILE_EXTENSIONS

        extensions = tuple(extensions)

        return await asyncio.to_thread(
            lambda: [str(path) for path in Path(source).glob("**/*") if path.suffix in extensions]
        )


class DirectoryRuleLoader(RuleLoader):
    """
    DirectoryRuleLoader is responsible for loading rules from a directory recursively.
    The directory can contain multiple rule files with supported extensions.
    In every rule file, multiple rules can be defined.
    Supported extensions are defined in the RULE_FILE_EXTENSIONS constant.

    Parameters
    ----------
    source : str
      The path to the directory containing the rule files.
    processor_name : str
      The name of the processor that the rules belong to.
    """

    async def load_rules(self) -> list[Rule]:
        """
        Generate and return a list of rules from the specified directory asynchronously.

        Returns
        -------
        list of Rule
          A list of Rule objects created from the rule files in the directory recursively.
        """
        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")

        rule_files = await self.files_by_extensions(self.source)
        rule_lists = []

        for file in rule_files:
            rule_lists.append(
                await FileRuleLoader(
                    str(file),
                    self.processor_name,
                ).load_rules()
            )

        return list(itertools.chain(*rule_lists))

    async def load_rule_definitions(self) -> list[dict]:
        """
        Generate and return a list of dicts reflecting rule definitions from
        the specified directory asynchronously.

        Returns
        -------
        list of dict
          A list of rule definitions created from the rule files in the directory recursively.
        """
        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")

        rule_files = await self.files_by_extensions(self.source)
        rule_definitions = []

        for file in rule_files:
            rule_definitions.append(
                await FileRuleLoader(
                    str(file),
                    self.processor_name,
                ).load_rule_definitions()
            )

        return list(itertools.chain(*rule_definitions))


class FileRuleLoader(RuleLoader):
    """FileRuleLoader is responsible for loading rules from a file.
    The file can contain multiple rules defined in either JSON or YAML format.

    Parameters
    ----------
    source : str
      The path to the file containing the rule definitions.
    processor_name : str
      The name of the processor that the rules belong to.
    """

    async def load_rules(self) -> list[Rule]:
        """Retrieve a list of rules asynchronously.
        This method processes the rule definitions and returns a list of Rule objects.
        It ensures that the source attribute is a string before proceeding.

        Returns
        -------
        list[Rule]
          A list of Rule objects generated from the rule definitions.

        Raises
        ------
        TypeError
          If the source attribute is not a string.
        """
        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")

        try:
            return list(
                itertools.chain(
                    *[
                        await DictRuleLoader(
                            rule_definition,
                            self.processor_name,
                        ).load_rules()
                        for rule_definition in await self.load_rule_definitions()
                    ]
                )
            )
        except ValueError as error:
            logger.warning(
                "Loading rules from %s failed: %s -> Skipping.",
                self.source,
                error,
            )

        return []

    async def load_rule_definitions(self) -> list[dict]:
        rule_definitions: list[dict] | dict = []

        if not isinstance(self.source, str):
            raise TypeError(f"Expected a string, got {type(self.source)}")

        if self.source.endswith(".yaml") or self.source.endswith(".yml"):
            rule_definitions = await GetterFactory.from_string(self.source).get_yaml()
        elif self.source.endswith(".json") and not self.source.endswith("_test.json"):
            rule_definitions = await GetterFactory.from_string(self.source).get_json()

        if not isinstance(rule_definitions, list):
            rule_definitions = [rule_definitions]

        return rule_definitions


class DictRuleLoader(RuleLoader):
    """DictRuleLoader is responsible for loading a rule from a dictionary.
    The dictionary should reflect a valid rule definition.

    Parameters
    ----------
    source : dict
      The dictionary containing the rule definition.
    processor_name : str
      The name of the processor that the rules belong to.
    """

    async def load_rules(self) -> list[Rule]:
        """Generate and return a list of rules from the specified
        dictionary.

        Returns
        -------
        list of Rule
          A list with one Rule object created from the dictionary.
        """
        from logprep.registry import Registry  # pylint: disable=import-outside-toplevel

        if not isinstance(self.source, dict):
            raise TypeError(f"Expected a dictionary, got {type(self.source)}")

        rule_class = Registry.get_rule_class_by_rule_definition(self.source)

        return [
            rule_class.create_from_dict(
                self.source,
                self.processor_name,
            )
        ]
