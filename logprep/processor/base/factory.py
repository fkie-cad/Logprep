"""This modules contains functionality for creating processors of given type."""

from logging import Logger


class BaseFactory:
    """Create processors of given type."""

    processor_type = None
    rule_type = None

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger):
        raise NotImplementedError

    @staticmethod
    def _add_defaults_to_configuration(configuration: dict):
        if 'include_parent_labels' not in configuration:
            configuration['include_parent_labels'] = False  # default

    @staticmethod
    def _check_configuration(configuration: dict):
        raise NotImplementedError
