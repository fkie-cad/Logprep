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
from logprep.ng.event.sre_event import SreEvent
from logprep.ng.framework.pipeline import Pipeline
from logprep.util.configuration import Configuration


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
        # config["documents"] = [LogEvent({"order": 0}, original=b"")]
        # self.dummy_input_connector = Factory.create({"Test Instance Name": config})

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

    def test_passes_timeout_parameter_to_input_get_next(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = LogEvent({"order": 0}, original=b"")
        self.pipeline.process_pipeline()
        timeout = self.logprep_config.timeout
        self.pipeline._input.get_next.assert_called_with(timeout)

    def test_passes_timeout_parameter_to_input_get_next2(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = LogEvent({"order": 0}, original=b"")
        self.pipeline.process_pipeline()
        timeout = self.logprep_config.timeout
        self.pipeline._input.get_next.assert_called_with(timeout)

    def test_pipeline_iterates_over_events(self, _):
        self.pipeline._setup()
        events = [LogEvent({"order": 0}, original=b""), LogEvent({"order": 1}, original=b"")]
        self.pipeline._input.get_next.side_effect = events

        pipeline_iter = iter(self.pipeline)
        result1 = next(pipeline_iter)
        result2 = next(pipeline_iter)
        assert result1 == LogEvent({"order": 0}, original=b"")
        assert result2 == LogEvent({"order": 1}, original=b"")
        assert result1.state.current_state is EventStateType.PROCESSED
        assert result2.state.current_state is EventStateType.PROCESSED

    def test_process_events_changes_event_states(self, _):
        self.pipeline._setup()
        event = LogEvent({"order": 0}, original=b"")
        event = mock.MagicMock()

        with mock.patch("logprep.ng.framework.pipeline.PipelineResult") as mock_pipeline_result:
            mock_result = mock.MagicMock()
            mock_pipeline_result.return_value = mock_result
            self.pipeline.process_event(event)
            assert event.state.next_state.call_count == 1

    def test_process_pipeline_changes_event_states(self, _):

        self.pipeline._setup()

        mock_event = mock.MagicMock()
        mock_event.state = mock.MagicMock()

        self.pipeline._input = mock.MagicMock()
        self.pipeline._input.get_next.return_value = mock_event
        self.pipeline.process_event = mock.MagicMock()

        self.pipeline.process_pipeline()
        assert mock_event.state.next_state.call_count == 2

    def test_process_pipeline_changes_event_states_failed_successfully(self, _):

        def mock_process_event(event):
            event.state.next_state()

        self.pipeline._setup()

        event = LogEvent({"order": 0}, original=b"")

        self.pipeline._input = mock.MagicMock()
        self.pipeline._input.get_next.return_value = event
        self.pipeline.process_event = mock_process_event

        self.pipeline.process_pipeline()
        assert event.state.current_state == EventStateType.PROCESSED

    def test_process_pipeline_changes_event_states_failed(self, _):

        def mock_process_event(event):
            event.state.next_state()

        self.pipeline._setup()

        event = LogEvent({"order": 0}, original=b"")
        event.errors = [Exception]

        self.pipeline._input = mock.MagicMock()
        self.pipeline._input.get_next.return_value = event
        self.pipeline.process_event = mock_process_event

        self.pipeline.process_pipeline()
        assert event.state.current_state == EventStateType.FAILED

    def test_extra_data_event_is_passed_to_store_custom(self, _):
        self.pipeline._logprep_config.pipeline = [
            {"dummy": {"type": "ng_dummy_processor"}},
            {"dummy": {"type": "ng_dummy_processor"}},
        ]

        outputs = ({"name": "sre_topic"},)
        data = {"foo": "bar"}
        sre_event = SreEvent(data=data, outputs=outputs)

        self.pipeline._setup()
        event = LogEvent({"order": 0}, original=b"")
        self.pipeline._input.get_next.return_value = event
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="", data=[sre_event]
        )
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert event.extra_data == [sre_event]
