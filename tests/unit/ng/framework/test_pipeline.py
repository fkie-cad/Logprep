# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-few-public-methods
import copy
from unittest import mock

import pytest

from logprep.abc.input import Input
from logprep.abc.processor import ProcessorResult
from logprep.ng.abc.processor import Processor
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.ng.event.sre_event import SreEvent
from logprep.ng.framework.pipeline import Pipeline
from logprep.util.configuration import Configuration


class MockInput:
    def __init__(self, iterable):
        self._iterator = iter(iterable)
        self.backlog = SetEventBacklog()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iterator)


class ConfigurationForTests:
    logprep_config = Configuration(
        **{
            "timeout": 0.001,
            "input": {
                "ng_dummy": {
                    "type": "ng_dummy_input",
                    "documents": [
                        LogEvent({"order": 0}, original=b""),
                        LogEvent({"order": 1}, original=b""),
                    ],
                }
            },
            "pipeline": [
                {"mock_processor1": {"proc": "conf"}},
                {"mock_processor2": {"proc": "conf"}},
            ],
        }
    )
    logprep_config._metrics = mock.MagicMock()


def get_mock_create():
    """
    Create a new mock_create magic mock with a default processor result. Is applied for every
    test.
    """

    def create_component(config):
        _, config = config.popitem()
        component = None
        match config:
            case {"type": component_type} if "input" in component_type:
                component = mock.create_autospec(spec=Input)
            case _:
                component = mock.create_autospec(spec=Processor)
                component.process.return_value = mock.create_autospec(spec=ProcessorResult)
        component._called_config = config
        return component

    return create_component


@pytest.fixture(name="mock_processor")
def get_mock_processor():
    mock_create = get_mock_create()
    return mock_create({"mock_processor": {"type": "mock_processor"}})


@mock.patch("logprep.factory.Factory.create", new_callable=get_mock_create)
class TestPipeline(ConfigurationForTests):
    def setup_method(self):
        self._check_failed_stored = None

        config = copy.deepcopy(self.logprep_config)
        self.pipeline = Pipeline(
            config=config,
        )

    def test_pipeline_property_returns_pipeline(self, _):
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        assert isinstance(self.pipeline._pipeline[0], Processor)
        assert isinstance(self.pipeline._pipeline[1], Processor)

    def test_setup_calls_setup_on_pipeline_processors(self, _):
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        for processor in self.pipeline._pipeline:
            processor.setup.assert_called()

    def test_process_pipeline_yields_results(self, _):
        inputs = [
            LogEvent({"order": 0}, original=b""),
            LogEvent({"order": 1}, original=b""),
        ]
        self.pipeline._setup()
        self.pipeline._input = MockInput(inputs)
        result = list(self.pipeline.process_pipeline())
        assert result == inputs
        assert result[0].state.current_state is EventStateType.PROCESSED

    def test_process_pipeline_iterates(self, _):
        inputs = [
            LogEvent({"order": 0}, original=b""),
            LogEvent({"order": 1}, original=b""),
        ]
        self.pipeline._setup()
        self.pipeline._input = iter(inputs)
        for i, result in enumerate(self.pipeline):
            assert result == inputs[i]

    def test_process_pipeline_changes_states_successfully(self, _):
        inputs = [
            LogEvent({"order": 0}, original=b""),
            LogEvent({"order": 1}, original=b""),
        ]
        self.pipeline._setup()
        self.pipeline._input = MockInput(inputs)
        result = list(self.pipeline.process_pipeline())

        assert result[0].state.current_state is EventStateType.PROCESSED
        assert result[1].state.current_state is EventStateType.PROCESSED

    def test_process_pipeline_changes_states_failed(self, _):
        inputs = [
            LogEvent({"order": 0}, original=b""),
            LogEvent({"order": 1}, original=b""),
        ]
        inputs[0].errors = [Exception]
        self.pipeline._setup()
        self.pipeline._input = MockInput(inputs)
        result = list(self.pipeline.process_pipeline())

        assert result[0].state.current_state is EventStateType.FAILED
        assert result[1].state.current_state is EventStateType.PROCESSED

    def test_extra_data_event_is_registered_in_backlog(self, _):
        outputs = ({"name": "sre_topic"},)
        data = {"foo": "bar"}
        sre_event = SreEvent(data=data, outputs=outputs)

        inputs = [
            LogEvent({"order": 0}, original=b"", extra_data=[sre_event]),
            LogEvent({"order": 1}, original=b""),
        ]

        self.pipeline._setup()
        self.pipeline._input = MockInput(inputs)

        _ = list(self.pipeline.process_pipeline())

        assert len(self.pipeline._input.backlog.backlog) == 1
        assert sre_event in self.pipeline._input.backlog.backlog

    def test_multiple_extra_data_event_is_registered_in_backlog(self, _):
        outputs = ({"name": "sre_topic1"},)
        data1 = {"foo": "bar1"}
        data2 = {"foo": "bar2"}
        sre_event1 = SreEvent(data=data1, outputs=outputs)
        sre_event2 = SreEvent(data=data2, outputs=outputs)

        inputs = [
            LogEvent({"order": 0}, original=b"", extra_data=[sre_event1]),
            LogEvent({"order": 1}, original=b"", extra_data=[sre_event2]),
        ]

        self.pipeline._setup()
        self.pipeline._input = MockInput(inputs)

        _ = list(self.pipeline.process_pipeline())

        assert len(self.pipeline._input.backlog.backlog) == 2
        assert sre_event1 in self.pipeline._input.backlog.backlog
        assert sre_event2 in self.pipeline._input.backlog.backlog
