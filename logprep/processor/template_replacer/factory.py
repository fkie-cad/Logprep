"""This module contains a factory for TemplateReplacer processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.template_replacer.processor import TemplateReplacer


class TemplateReplacerFactory(BaseFactory):
    """Create template replacer."""

    mandatory_items = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> TemplateReplacer:
        """Create a template replacer."""
        TemplateReplacerFactory._check_configuration(configuration)

        return TemplateReplacer(
            name=name,
            configuration=configuration,
            logger=logger,
        )

    @staticmethod
    def _check_configuration(configuration: dict):
        TemplateReplacerFactory._check_common_configuration(
            "template_replacer", TemplateReplacerFactory.mandatory_items, configuration
        )
