import warnings
from logprep.processor.processor_registry import ProcessorRegistry


def test_get_processor_class_throws_deprecation_warning():
    with warnings.catch_warnings(record=True) as warning_messages:
        ProcessorRegistry.get_processor_class("delete")
        assert len(warning_messages) == 1
        assert isinstance(warning_messages[0], warnings.WarningMessage)
        assert (
            str(warning_messages[0].message)
            == "delete processor is deprecated and will be removed in a future release. Please use deleter instead."
        )
