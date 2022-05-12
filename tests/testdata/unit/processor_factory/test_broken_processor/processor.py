# pylint: disable=missing-docstring
# pylint: disable=abstract-method
from logprep.processor.base.exceptions import SkipImportError
from logprep.processor.base.processor import RuleBasedProcessor


class TestBrokenProcessor(RuleBasedProcessor):
    raise SkipImportError("test_broken_processor")
