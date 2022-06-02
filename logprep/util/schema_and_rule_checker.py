# !/usr/bin/python3

"""Runner for testing schemas and rules"""

from typing import Optional, List
from collections.abc import Iterable

from argparse import ArgumentParser
from logging import Logger
from os import walk
from os.path import join
from json.decoder import JSONDecodeError

from colorama import Fore

from logprep.util.configuration import Configuration

from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    MismatchedRuleDefinitionError,
)
from logprep.processor.base.rule import Rule
from logprep.abc import Processor
from logprep.processor.labeler.labeling_schema import LabelingSchema, InvalidLabelingSchemaFileError
from logprep.filter.lucene_filter import LuceneFilterError


class SchemaAndRuleChecker:
    """Check validity of schema and rules."""

    def __init__(self):
        self.errors = []

    @staticmethod
    def _parse_command_line_arguments():
        argument_parser = ArgumentParser()
        argument_parser.add_argument("--labeling-schema", help="Path to labeling schema file")
        argument_parser.add_argument("--labeling-rules", help="Path to labeling rule directory")
        argument_parser.add_argument(
            "--normalization-rules", help="Path to normalizer rule directory"
        )
        argument_parser.add_argument(
            "--pseudonymization-rules", help="Path to pseudonymizer rule directory"
        )

        arguments = argument_parser.parse_args()
        return arguments

    def _print_valid(self, msg: str):
        if not self.errors:
            print(Fore.GREEN + msg)
            print(Fore.RESET, end="")

    def _print_errors(self):
        for error in self.errors:
            print(Fore.RED + error)
        print(Fore.RESET, end="")

    @staticmethod
    def init_additional_grok_patterns(rule_class: Rule, config: dict):
        if isinstance(config, dict) and config.get("grok_patterns"):
            rule_class.additional_grok_patterns = config.get("grok_patterns")

    @staticmethod
    def _get_pipeline(config_path: str) -> Iterable:
        config_path = Configuration().create_from_yaml(config_path)
        pipeline = config_path["pipeline"]
        return pipeline

    def _get_rule_and_schema_paths_from_config(self, config_path: str, processor_type: Processor):
        pipeline = self._get_pipeline(config_path)
        for processor in pipeline:
            options = next(iter(processor.values()))
            if options["type"] == processor_type:
                rules = []
                if options.get("rules") is not None:
                    rules = options["rules"]
                elif None not in (options.get("specific_rules"), options.get("generic_rules")):
                    rules = options["specific_rules"] + options["generic_rules"]
                yield options.get("schema"), rules

    def _get_config_values(self, config_path, processor_type):
        pipeline = self._get_pipeline(config_path)
        for processor in pipeline:
            options = next(iter(processor.values()))
            if options["type"] == processor_type:
                return options

    @staticmethod
    def _log_error_message(error: KeyError, logger: Logger):
        logger.critical(
            f"Key {error} does not exist in configuration file! Rules can't be " f"validated!"
        )

    def validate_rules(
        self, config_path: str, processor_type: Processor, rule_class: Rule, logger: Logger
    ) -> bool:
        """Validate rule for processor.

        Parameters
        ----------
        config_path : dict
            Path to configuration file
        processor_type : Processor
            Type of processor to validate rules for.
        rule_class : Rule
            Type of rule to validate rules for.
        logger : Logger
            Logger to use.

        Returns
        -------
        valid : bool
            Signifies if rule is valid or not.

        """
        try:
            options = self._get_config_values(config_path, processor_type)
            self.init_additional_grok_patterns(rule_class, options)

            valid = True
            for schema_path, rules_paths in self._get_rule_and_schema_paths_from_config(
                config_path, processor_type
            ):
                for rules_path in rules_paths:
                    valid = valid and self._validate_rules_in_path(
                        rules_path, processor_type, rule_class, schema_path
                    )
            return valid
        except KeyError as error:
            self._log_error_message(error, logger)

    def _validate_rules_in_path(
        self,
        path_rules: str,
        processor_type: Processor,
        rule_class: Rule,
        path_schema: str = None,
    ):
        number_of_checked_rules = 0
        for root, _, files in walk(path_rules):
            for file in files:
                number_of_checked_rules += 1
                rule_path = join(root, file)

                multi_rule = self.check_rule_creation_errors(rule_class, rule_path)
                self._validate_schema(multi_rule, path_schema, rule_path)
            self._print_schema_check_results(path_schema)
        if not self.errors:
            self._print_valid(
                f"Valid {processor_type} rules in {path_rules} "
                f"({number_of_checked_rules} rules checked)."
            )

        self._print_errors()
        return False if self.errors else True

    def _print_schema_check_results(self, path_schema: str):
        if path_schema:
            self._print_valid(f"Valid labeler schema in {path_schema}.")

    def _validate_schema(self, multi_rule: list, path_schema: str, rule_path: str):
        if path_schema:
            schema = self._validate_schema_definition(path_schema)
            if schema and multi_rule:
                for rule in multi_rule:
                    try:
                        rule.conforms_to_schema(schema)
                    except MismatchedRuleDefinitionError as error:
                        self.errors.append(
                            f"Mismatch of rule definition in {rule_path} with schema in "
                            f"{path_schema}: {str(error)}"
                        )

    def _validate_schema_definition(self, path_schema: str) -> LabelingSchema:
        try:
            schema = LabelingSchema.create_from_file(path_schema)
        except InvalidLabelingSchemaFileError as error:
            self.errors.append(str(error))
        else:
            return schema

    def check_rule_creation_errors(self, rule_class: Rule, rule_path: str) -> Optional[List[Rule]]:
        """Check for error on rule creation.

        Parameters
        ----------
        rule_class : Rule
            Class of rule to be tested.
        rule_path : str
            Path to rule to be tested.

        Returns
        -------
        rule : Rule
            Rule object.

        """
        rule = None
        try:
            if rule_path.endswith(".json") or rule_path.endswith(".yml"):
                if not rule_path.endswith("_test.json"):
                    rule = rule_class.create_rules_from_file(rule_path)
        except InvalidRuleDefinitionError as error:
            self.errors.append("Invalid rule definition in {}: {}".format(rule_path, str(error)))
        except JSONDecodeError as error:
            self.errors.append("JSON decoder Error in {}: {}".format(rule_path, str(error)))
        except LuceneFilterError as error:
            self.errors.append("Lucene Filter Error in {}: {}".format(rule_path, str(error)))
        return rule
