"""This module contains functionality for resolving log event values using regex lists."""
from typing import List
from logging import Logger, DEBUG


from multiprocessing import current_process

from ipaddress import ip_address

from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.geoip_enricher.rule import GeoIPEnricherRule

from logprep.util.processor_stats import ProcessorStats
from logprep.util.helper import add_field_to


class GeoIPEnricherError(BaseException):
    """Base class for GeoIPEnricher related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GeoIPEnricher ({name}): {message}")


class DuplicationError(GeoIPEnricherError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the GeoIPEnricher: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GeoIPEnricher(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, configuration: dict, logger: Logger):
        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config, logger)
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        geoip_db_path = configuration.get("db_path")
        self.ps = ProcessorStats()
        self.add_rules_from_directory(
            specific_rules_dirs=specific_rules_dirs,
            generic_rules_dirs=generic_rules_dirs,
        )
        self._city_db = database.Reader(geoip_db_path)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = GeoIPEnricherRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = GeoIPEnricherRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"generic rules ({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

    def describe(self) -> str:
        return f"GeoIPEnricher ({self._name})"

    @staticmethod
    def _normalize_empty(db_entry):
        return db_entry if db_entry else None

    def _try_getting_geoip_data(self, ip_string):
        if ip_string is None:
            return dict()

        try:
            geoip = dict()

            ip = str(ip_address(ip_string))
            ip_data = self._city_db.city(ip)

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
            return dict()

    def _apply_rules(self, event, rule):
        source_ip = rule.source_ip
        output_field = rule.output_field
        if source_ip:
            ip_string = self._get_dotted_field_value(event, source_ip)
            geoip_data = self._try_getting_geoip_data(ip_string)
            if geoip_data:
                adding_was_successful = add_field_to(event, output_field, geoip_data)

                if not adding_was_successful:
                    raise DuplicationError(self._name, [output_field])
