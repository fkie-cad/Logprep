"""This module contains errors related to ProcessorFactory."""


class ProcessorFactoryError(BaseException):
    """Base class for ProcessorFactory related exceptions."""


class InvalidConfigurationError(ProcessorFactoryError):
    """Raise if configuration is invalid."""


class NotExactlyOneEntryInConfigurationError(InvalidConfigurationError):
    """Raise if there is not exactly one processor definition per pipeline."""

    def __init__(self):
        super().__init__('There must be exactly one processor definition per pipeline entry.')


class InvalidConfigSpecificationError(InvalidConfigurationError):
    """Raise if the processor configuration was not specified as an object."""

    def __init__(self):
        super().__init__('The processor configuration must be specified as an object.')


class NoTypeSpecifiedError(InvalidConfigurationError):
    """Raise if the processor type specification is missing."""
    def __init__(self):
        super().__init__('The processor type specification is missing')


class UnknownProcessorTypeError(ProcessorFactoryError):
    """Raise if the processor type is unknown."""

    def __init__(self, processor_type=None):
        if processor_type:
            super().__init__(f'Unknown processor type \'{processor_type}\'')
        else:
            super().__init__('Unknown processor type')


class InvalidProcessorClassError(ProcessorFactoryError):
    """Raise if the processor type is not valid."""

    def __init__(self, processor_class):
        if processor_class:
            if len(processor_class) == 1:
                super().__init__(f'Processor class {processor_class} has no \'identifier\' field')
            else:
                super().__init__(f'Processor classes {processor_class} have no \'identifier\''
                                 f' field')
