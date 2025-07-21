# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

from unittest import mock

import pytest

from logprep.abc.processor import ProcessorResult
from logprep.ng.abc.input import Input
from logprep.ng.abc.processor import Processor
from logprep.ng.event.log_event import LogEvent
from logprep.ng.framework.pipeline import Pipeline
from logprep.util.configuration import Configuration


class ConfigurationForTests:
    logprep_config = Configuration(
        **{
            "timeout": 0.001,
            "input": {
                "ng_dummy": {
                    "type": "ng_dummy_input",
                    "documents": [],
                }
            },
            "pipeline": [
                {"mock_processor1": {"proc": "conf"}},
                {"mock_processor2": {"proc": "conf"}},
            ],
        }
    )


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

        # config = copy.deepcopy({"type": "ng_dummy_input", "documents": []})
        # config["repeat_documents"] = False
        # config["documents"] = [LogEvent({"order": 0}, original=b"")]
        # self.dummy_input_connector = Factory.create({"Test Instance Name": config})

        self.pipeline = Pipeline(
            config=self.logprep_config,
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
        self.pipeline._input.get_next.return_value = {}
        self.pipeline.process_pipeline()
        timeout = self.logprep_config.timeout
        self.pipeline._input.get_next.assert_called_with(timeout)

    ###########
    def test_pipeline_runs(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = LogEvent({"order": 0}, original=b"")
        self.pipeline.run()
