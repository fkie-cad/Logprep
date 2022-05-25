"""This module contains a factory for GenericResolver processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.geoip_enricher.processor import GeoipEnricher


class GeoipEnricherFactory(BaseFactory):
    """Create generic resolver."""

    mandatory_fields = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GeoipEnricher:
        """Create a generic resolver."""
        GeoipEnricherFactory._check_configuration(configuration)

        geoip_enricher = GeoipEnricher(name=name, configuration=configuration, logger=logger)

        return geoip_enricher

    @staticmethod
    def _check_configuration(configuration: dict):
        GeoipEnricherFactory._check_common_configuration(
            "geoip_enricher", GeoipEnricherFactory.mandatory_fields, configuration
        )
