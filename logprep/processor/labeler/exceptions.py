from logprep.processor.processor_factory_error import InvalidConfigurationError


class LabelerError(BaseException):
    """Base class for Labeler related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'Labeler ({name}): {message}')


class LabelerConfigurationError(LabelerError):
    """Generic labeler configuration error."""


class NoLabelingSchemeDefinedError(LabelerError):
    """Raise if no labeling schema is defined."""

    def __init__(self, name: str):
        super().__init__(name, 'No labeling schema was loaded.')


class MustLoadRulesFirstError(LabelerError):
    """Raise if no rules were loaded."""

    def __init__(self, name: str):
        super().__init__(name, 'No rules were loaded.')


class InvalidLabelingSchemaError(LabelerConfigurationError):
    """Raise if labeling schema is invalid."""


class RuleDoesNotConformToLabelingSchemaError(LabelerConfigurationError):
    """Raise if rule does not conform to labeling schema."""

    def __init__(self, name: str, path: str):
        super().__init__(name,
                         f'Invalid rule file "{path}": Does not conform to labeling schema.')


class InvalidLabelerFactoryConfigurationError(InvalidConfigurationError):
    """Base class for LabelerFactory specific exceptions."""


class RulesDefinitionMissingError(InvalidLabelerFactoryConfigurationError):
    """Raise if no rule paths have been configured."""

    def __init__(self):
        super().__init__('The labeler configuration must contain at least one path to a rules '
                         'directory.')


class InvalidSchemaDefinitionError(InvalidLabelerFactoryConfigurationError):
    """Raise if file in path is not a valid schema definition file."""

    def __init__(self, message: str):
        super().__init__(f'schema does not point to a schema definition file: {message}')


class SchemaDefinitionMissingError(InvalidLabelerFactoryConfigurationError):
    """Raise if labeler configuration is not pointing to a schema definition file."""

    def __init__(self):
        super().__init__('The labeler configuration must point to a schema definition.')


class InvalidIncludeParentsValueError(InvalidLabelerFactoryConfigurationError):
    """Raise if 'include_parent_labels' is not a boolean value."""
    def __init__(self):
        super().__init__('"include_parent_labels" must be either true or false.')
