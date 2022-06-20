# pylint: disable=missing-docstring
# pylint: disable=abstract-method
from logprep.processor.base.exceptions import SkipImportError
from logprep.processor.base.rule import Rule
from logprep.abc import Processor


class TestBrokenProcessor(Processor):
    raise SkipImportError("test_broken_processor")

    def _apply_rules(self, event: dict, rule: Rule):
        pass
