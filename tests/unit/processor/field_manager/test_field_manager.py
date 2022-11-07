# pylint: disable=missing-docstring
from tests.unit.processor.base import BaseProcessorTestCase


class TestFieldManager(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "field_manager",
        "specific_rules": ["tests/testdata/unit/field_manager/specific_rules"],
        "generic_rules": ["tests/testdata/unit/field_manager/generic_rules"],
    }
