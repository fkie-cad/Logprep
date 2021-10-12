"""This module contains functionality for resolving log event values using regex lists."""
from time import time
from typing import List
from logging import Logger, DEBUG

from os import walk
from os.path import isdir, realpath, join

from multiprocessing import current_process

from ipaddress import ip_address

from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.geoip_enricher.rule import GeoIPEnricherRule
from logprep.processor.base.exceptions import (NotARulesDirectoryError, InvalidRuleDefinitionError,
                                               InvalidRuleFileError)

from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class GeoIPEnricherError(BaseException):
    """Base class for GeoIPEnricher related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f'GeoIPEnricher ({name}): {message}')


class DuplicationError(GeoIPEnricherError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = 'The following fields already existed and ' \
                  'were not overwritten by the Normalizer: '
        message += ' '.join(skipped_fields)

        super().__init__(name, message)


class GeoIPEnricher(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(self, name: str, tree_config: str, geoip_db_path: str, logger: Logger):
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._city_db = database.Reader(geoip_db_path)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(self, rule_paths: List[str]):
        """Add rules from given directory."""
        for path in rule_paths:
            if not isdir(realpath(path)):
                raise NotARulesDirectoryError(self._name, path)

            for root, _, files in walk(path):
                json_files = []
                for file in files:
                    if (file.endswith('.json') or file.endswith('.yml')) and not file.endswith(
                            '_test.json'):
                        json_files.append(file)
                for file in json_files:
                    rules = self._load_rules_from_file(join(root, file))
                    for rule in rules:
                        self._tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(f'{self.describe()} loaded {self._tree.rule_counter} rules '
                               f'({current_process().name})')

        self.ps.setup_rules([None] * self._tree.rule_counter)
    # pylint: enable=arguments-differ

    def _load_rules_from_file(self, path: str):
        try:
            return GeoIPEnricherRule.create_rules_from_file(path)
        except InvalidRuleDefinitionError as error:
            raise InvalidRuleFileError(self._name, path) from error

    def describe(self) -> str:
        return f'GeoIPEnricher ({self._name})'

    @TimeMeasurement.measure_time('geoip_enricher')
    def process(self, event: dict):
        self._events_processed += 1
        self.ps.update_processed_count(self._events_processed)

        self._event = event

        for rule in self._tree.get_matching_rules(event):
            begin = time()
            self._apply_rules(event, rule)
            processing_time = float('{:.10f}'.format(time() - begin))
            idx = self._tree.get_rule_id(rule)
            self.ps.update_per_rule(idx, processing_time)

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
                geoip['type'] = 'Feature'
                properties = {}

                if ip_data.location:
                    longitude = self._normalize_empty(ip_data.location.longitude)
                    latitude = self._normalize_empty(ip_data.location.latitude)
                    if longitude and latitude:
                        geoip['geometry'] = {
                            'type': 'Point',
                            'coordinates': [longitude, latitude]
                        }

                    accuracy_radius = self._normalize_empty(ip_data.location.accuracy_radius)
                    if accuracy_radius:
                        properties['accuracy_radius'] = accuracy_radius

                if ip_data.continent:
                    continent = self._normalize_empty(ip_data.continent.name)
                    if continent:
                        properties['continent'] = continent

                if ip_data.country:
                    country = self._normalize_empty(ip_data.country.name)
                    if country:
                        properties['country'] = country

                if ip_data.city:
                    city = self._normalize_empty(ip_data.city.name)
                    if city:
                        properties['city'] = city

                if ip_data.postal:
                    postal_code = self._normalize_empty(ip_data.postal.code)
                    if postal_code:
                        properties['postal_code'] = postal_code

                if ip_data.subdivisions:
                    if ip_data.subdivisions.most_specific:
                        properties['subdivision'] = ip_data.subdivisions.most_specific.name

                if properties:
                    geoip['properties'] = properties

                return geoip

        except (ValueError, AddressNotFoundError):
            return dict()

    def _apply_rules(self, event, rule):
        source_ip = rule.source_ip
        if source_ip:
            ip_string = self._get_dotted_field_value(event, source_ip)
            geoip_data = self._try_getting_geoip_data(ip_string)
            if geoip_data:
                if 'geoip' not in event:
                    event['geoip'] = geoip_data
                elif event['geoip'] != geoip_data:
                    raise DuplicationError(self._name, ['geoip'])
