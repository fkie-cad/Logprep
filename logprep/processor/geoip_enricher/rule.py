"""This module is used to resolve field values from documents via a list."""

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class GeoipEnricherRuleError(InvalidRuleDefinitionError):
    """Base class for GeoipEnricher rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GeoipEnricher rule ({message}): ")


class InvalidGeoipEnricherDefinition(GeoipEnricherRuleError):
    """Raise if GeoipEnricher definition invalid."""

    def __init__(self, definition):
        message = f"The following GeoipEnricher definition is invalid: {definition}"
        super().__init__(message)


class GeoipEnricherRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, geoip_enricher_cfg: dict):
        super().__init__(filter_rule)

        if "output_field" in geoip_enricher_cfg.keys():
            self._output_field = geoip_enricher_cfg["output_field"]
        else:
            self._output_field = "geoip"

        self._source_ip = geoip_enricher_cfg["source_ip"]

    def __eq__(self, other: "GeoipEnricherRule") -> bool:
        return (other.filter == self._filter) and (self.source_ip == other.source_ip)

    # pylint: disable=C0111
    @property
    def source_ip(self) -> dict:
        return self._source_ip

    # pylint: enable=C0111

    @property
    def output_field(self) -> dict:
        return self._output_field

    @staticmethod
    def _create_from_dict(rule: dict) -> "GeoipEnricherRule":
        GeoipEnricherRule._check_rule_validity(rule, "geoip_enricher")
        GeoipEnricherRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return GeoipEnricherRule(filter_expression, rule["geoip_enricher"])

    @staticmethod
    def _check_if_valid(rule: dict):
        geoip_enricher_cfg = rule["geoip_enricher"]
        for field in ("source_ip",):
            if not isinstance(geoip_enricher_cfg[field], str):
                raise InvalidGeoipEnricherDefinition(
                    '"{}" value "{}" is not a string!'.format(field, geoip_enricher_cfg[field])
                )
        if "output_field" in geoip_enricher_cfg.keys():
            for field in ("output_field",):
                if not isinstance(geoip_enricher_cfg[field], str):
                    raise InvalidGeoipEnricherDefinition(
                        '"{}" value "{}" is not a string!'.format(field, geoip_enricher_cfg[field])
                    )
