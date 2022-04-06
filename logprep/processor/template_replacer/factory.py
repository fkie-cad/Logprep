"""This module contains a factory for TemplateReplacer processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.template_replacer.processor import TemplateReplacer


class TemplateReplacerFactory(BaseFactory):
    """Create template replacer."""

    @staticmethod
    def create(name: str, configuration: dict, logger) -> TemplateReplacer:
        """Create a template replacer."""
        TemplateReplacerFactory._check_configuration(configuration)

        template_replacer = TemplateReplacer(
            name,
            configuration.get("tree_config"),
            configuration["template"],
            configuration["pattern"],
            logger,
        )
        template_replacer.add_rules_from_directory(configuration["rules"])

        return template_replacer

    @staticmethod
    def _check_configuration(configuration: dict):
        TemplateReplacerFactory._check_common_configuration(
            "template_replacer", ["rules"], configuration
        )
