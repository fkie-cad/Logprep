# pylint: disable=missing-docstring
# pylint: disable=unused-import
# pylint: disable=abstract-method
from logprep.processor.base.factory import BaseFactory

# The import below must exist
from tests.testdata.unit.processor_factory.test_processor.processor import TestProcessor


class TestProcessorFactory(BaseFactory):
    pass
