from unittest import mock

import pytest

from logprep.ng.manager import PipelineManager
from logprep.ng.util.configuration import Configuration


def _create_configuration() -> mock.NonCallableMagicMock:
    configuration = mock.NonCallableMagicMock(spec=Configuration)
    configuration.input = {"input": {}}
    configuration.pipeline = [{"first": {}}, {"second": {}}]
    configuration.output = {"output": {}}
    configuration.error_output = {}
    configuration.workflow = {}
    configuration.version = "test"
    return configuration


def _create_component() -> mock.NonCallableMagicMock:
    component = mock.NonCallableMagicMock()
    component.setup = mock.AsyncMock()
    component.shut_down = mock.AsyncMock()
    return component


async def test_setup_shuts_down_components_if_component_setup_fails():
    configuration = _create_configuration()

    input_connector = _create_component()
    input_connector.preprocessor = mock.NonCallableMagicMock()

    first_processor = _create_component()
    second_processor = _create_component()
    second_processor.setup.side_effect = RuntimeError("setup failed")

    output = _create_component()

    components = [
        input_connector,
        first_processor,
        second_processor,
        output,
    ]

    recorder = mock.MagicMock()
    recorder.__enter__.return_value = recorder
    recorder.create.side_effect = components
    recorder.components = components

    manager = PipelineManager(configuration)

    with mock.patch(
        "logprep.ng.manager.Factory.recorder",
        return_value=recorder,
    ):
        with pytest.raises(RuntimeError, match="setup failed"):
            await manager.setup()

    for component in components:
        component.shut_down.assert_awaited_once()


async def test_setup_shuts_down_components_if_orchestrator_creation_fails():
    configuration = _create_configuration()

    input_connector = _create_component()
    input_connector.preprocessor = mock.NonCallableMagicMock()

    first_processor = _create_component()
    second_processor = _create_component()

    output = _create_component()

    components = [
        input_connector,
        first_processor,
        second_processor,
        output,
    ]

    recorder = mock.MagicMock()
    recorder.__enter__.return_value = recorder
    recorder.create.side_effect = components
    recorder.components = components

    manager = PipelineManager(configuration)

    with (
        mock.patch(
            "logprep.ng.manager.Factory.recorder",
            return_value=recorder,
        ),
        mock.patch(
            "logprep.ng.manager.create_orchestrator",
            side_effect=RuntimeError("orchestrator failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="orchestrator failed"):
            await manager.setup()

    for component in components:
        component.setup.assert_awaited_once()
        component.shut_down.assert_awaited_once()
