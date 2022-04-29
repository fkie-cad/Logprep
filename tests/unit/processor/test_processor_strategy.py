# pylint: disable=missing-docstring
from unittest import mock

from logprep.processor.processor_strategy import SpecificGenericProcessStrategy


class TestSpecificGenericProcessStrategy:
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_generic"
    )
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_specific"
    )
    def test_process(self, mock_process_specific, mock_process_generic):
        strategy = SpecificGenericProcessStrategy()
        strategy.process({}, processor_stats=mock.Mock())
        mock_process_generic.assert_called()
        mock_process_specific.assert_called()

    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_generic"
    )
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_specific"
    )
    def test_process_specific_before_generic(self, mock_process_specific, mock_process_generic):
        call_order = []
        mock_process_specific.side_effect = lambda *a, **kw: call_order.append(
            mock_process_specific
        )
        mock_process_generic.side_effect = lambda *a, **kw: call_order.append(mock_process_generic)
        strategy = SpecificGenericProcessStrategy()
        strategy.process({}, processor_stats=mock.Mock())
        assert call_order == [mock_process_specific, mock_process_generic]
