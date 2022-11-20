from tests.unit.processor.base import BaseProcessorTestCase


class TestCalculator(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "calculator",
        "specific_rules": ["tests/testdata/unit/calculator/specific_rules"],
        "generic_rules": ["tests/testdata/unit/calculator/generic_rules"],
    }
