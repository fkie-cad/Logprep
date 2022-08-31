import warnings
from logprep.processor.processor_registry import ProcessorRegistry


def test_get_processor_class_throws_deprecation_warning():
    with warnings.catch_warnings(record=True) as w:
        ProcessorRegistry.get_processor_class("delete")
        assert len(w) == 1
        assert isinstance(w[0], warnings.WarningMessage)
        assert (
            str(w[0].message)
            == "delete processor is deprecated and will be removed in a future release. Please use deleter instead."
        )
