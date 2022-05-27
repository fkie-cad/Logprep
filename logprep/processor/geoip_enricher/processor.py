"""This module contains functionality for resolving log event values using regex lists."""
from ipaddress import ip_address
from logging import Logger
import os
import sys
from typing import List
from attr import define, field, validators

from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.abc import Processor
from logprep.processor.geoip_enricher.rule import GeoipEnricherRule
from logprep.util.helper import add_field_to


class GeoipEnricherError(BaseException):
    """Base class for GeoipEnricher related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GeoipEnricher ({name}): {message}")


class DuplicationError(GeoipEnricherError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the GeoipEnricher: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GeoipEnricher(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """geoip_enricher config"""

        db_path: str = field(validator=[validators.instance_of(str)])

    __slots__ = ["_city_db"]

    _city_db: database.Reader

    rule_class = GeoipEnricherRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        geoip_db_path = configuration.get("db_path")
        self._city_db = database.Reader(geoip_db_path)

    @staticmethod
    def _normalize_empty(db_entry):
        return db_entry if db_entry else None

    def _try_getting_geoip_data(self, ip_string):
        if ip_string is None:
            return {}

        try:
            geoip = {}

            ip_addr = str(ip_address(ip_string))
            ip_data = self._city_db.city(ip_addr)

            if ip_data:
                geoip["type"] = "Feature"
                properties = {}

                if ip_data.location:
                    longitude = self._normalize_empty(ip_data.location.longitude)
                    latitude = self._normalize_empty(ip_data.location.latitude)
                    if longitude and latitude:
                        geoip["geometry"] = {
                            "type": "Point",
                            "coordinates": [longitude, latitude],
                        }

                    accuracy_radius = self._normalize_empty(ip_data.location.accuracy_radius)
                    if accuracy_radius:
                        properties["accuracy_radius"] = accuracy_radius

                if ip_data.continent:
                    continent = self._normalize_empty(ip_data.continent.name)
                    if continent:
                        properties["continent"] = continent

                if ip_data.country:
                    country = self._normalize_empty(ip_data.country.name)
                    if country:
                        properties["country"] = country

                if ip_data.city:
                    city = self._normalize_empty(ip_data.city.name)
                    if city:
                        properties["city"] = city

                if ip_data.postal:
                    postal_code = self._normalize_empty(ip_data.postal.code)
                    if postal_code:
                        properties["postal_code"] = postal_code

                if ip_data.subdivisions:
                    if ip_data.subdivisions.most_specific:
                        properties["subdivision"] = ip_data.subdivisions.most_specific.name

                if properties:
                    geoip["properties"] = properties

                return geoip

        except (ValueError, AddressNotFoundError):
            return {}

    def _apply_rules(self, event, rule):
        source_ip = rule.source_ip
        output_field = rule.output_field
        if source_ip:
            ip_string = self._get_dotted_field_value(event, source_ip)
            geoip_data = self._try_getting_geoip_data(ip_string)
            if geoip_data:
                adding_was_successful = add_field_to(event, output_field, geoip_data)

                if not adding_was_successful:
                    raise DuplicationError(self.name, [output_field])
