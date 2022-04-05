"""This module contains a factory for GenericResolver processors."""

from logprep.processor.base.factory import BaseFactory
from logprep.processor.geoip_enricher.processor import GeoIPEnricher


class GeoIPEnricherFactory(BaseFactory):
    """Create generic resolver."""

    mandatory_fields = ["specific_rules", "generic_rules"]

    @staticmethod
    def create(name: str, configuration: dict, logger) -> GeoIPEnricher:
        """Create a generic resolver."""
        GeoIPEnricherFactory._check_configuration(configuration)

        geoip_enricher = GeoIPEnricher(
            name=name, configuration=configuration, logger=logger
        )

        return geoip_enricher

    @staticmethod
    def _check_configuration(configuration: dict):
        GeoIPEnricherFactory._check_common_configuration(
            "geoip_enricher", GeoIPEnricherFactory.mandatory_fields, configuration
        )
