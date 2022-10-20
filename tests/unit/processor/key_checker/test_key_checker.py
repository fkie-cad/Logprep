from tests.unit.processor.base import BaseProcessorTestCase


class TestKeyChecker(BaseProcessorTestCase):
    timeout = 0.01

    CONFIG = {
        "type": "key_checker",
        "specific_rules": ["tests/testdata/unit/key_checker/"],
        "generic_rules": ["tests/testdata/unit/key_checker/"],
    }
