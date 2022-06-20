# pylint: disable=missing-docstring
# pylint: disable=unused-import
# pylint: disable=abstract-method
from logprep.processor.base.factory import BaseFactory

# The import below must exist
from tests.testdata.unit.processor_factory.test_broken_processor.processor import (
    TestBrokenProcessor,
)


class TestBrokenProcessorFactory(BaseFactory):
    pass
