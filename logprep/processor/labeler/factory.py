"""This module contains a factory for labeler processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.labeler.processor import Labeler
from logprep.processor.processor_factory_error import UnknownProcessorTypeError
from logprep.processor.base.exceptions import (
    InvalidRuleFileError,
    NotARulesDirectoryError,
    KeyDoesnotExistInSchemaError,
    InvalidRuleConfigurationError,
)
from logprep.processor.labeler.exceptions import (
    InvalidSchemaDefinitionError,
    RuleDoesNotConformToLabelingSchemaError,
    InvalidConfigurationError,
    SchemaDefinitionMissingError,
    RulesDefinitionMissingError,
    InvalidIncludeParentsValueError,
)
from logprep.processor.labeler.rule import LabelingRule
from logprep.processor.labeler.labeling_schema import LabelingSchema, InvalidLabelingSchemaFileError


class LabelerFactory(BaseFactory):
    """Create labelers."""

    processor_type = Labeler
    rule_type = LabelingRule

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Labeler:
        """Create a labeler."""
        labeler = Labeler(name, configuration.get("tree_config"), logger)

        LabelerFactory._check_configuration(configuration)
        LabelerFactory._add_defaults_to_configuration(configuration)

        try:
            schema = LabelingSchema.create_from_file(configuration["schema"])
            labeler.set_labeling_scheme(schema)
        except InvalidLabelingSchemaFileError as error:
            raise InvalidSchemaDefinitionError(str(error)) from error

        try:
            labeler.add_rules_from_directory(
                configuration["rules"], include_parent_labels=configuration["include_parent_labels"]
            )
        except (
            InvalidRuleFileError,
            RuleDoesNotConformToLabelingSchemaError,
            NotARulesDirectoryError,
            KeyDoesnotExistInSchemaError,
        ) as error:
            raise InvalidRuleConfigurationError(str(error)) from error

        return labeler

    @staticmethod
    def _add_defaults_to_configuration(configuration: dict):
        if "include_parent_labels" not in configuration:
            configuration["include_parent_labels"] = False  # default

    @staticmethod
    def _check_configuration(configuration: dict):
        if "type" not in configuration:
            raise InvalidConfigurationError
        if (not isinstance(configuration["type"], str)) or (
            configuration["type"].lower() != "labeler"
        ):
            raise UnknownProcessorTypeError

        if "schema" not in configuration:
            raise SchemaDefinitionMissingError

        if "rules" not in configuration or not configuration["rules"]:
            raise RulesDefinitionMissingError

        if "include_parent_labels" in configuration and (
            not configuration["include_parent_labels"] in [True, False]
        ):
            raise InvalidIncludeParentsValueError
