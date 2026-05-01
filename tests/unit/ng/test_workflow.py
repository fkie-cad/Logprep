# pylint: disable=missing-docstring
# pylint: disable=protected-access

import asyncio
import typing
from collections.abc import AsyncGenerator, Sequence
from unittest import mock

import pytest

from logprep.abc.component import Component
from logprep.factory import Factory
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.connector.dummy.input import DummyInput
from logprep.ng.connector.dummy.output import DummyOutput
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.log_event import LogEvent
from logprep.ng.workflow import create_orchestrator
from logprep.util.typing import is_sequence_of


@pytest.fixture(name="input_events")
def get_input_mock():
    return [
        {"message": "Log message 1"},
        {"message": "Log message 2"},
        {"user": {"name": "John Doe"}},
    ]


@pytest.fixture(name="dummy_input", scope="function")
def get_dummy_input(input_events) -> DummyInput:
    return typing.cast(
        DummyInput,
        Factory.create(
            {
                "input": {
                    "type": "ng_dummy_input",
                    "documents": input_events,
                }
            }
        ),
    )


@pytest.fixture(name="processors")
async def get_processors_mock():
    processors = [
        Factory.create(
            {
                "processor": {
                    "type": "ng_generic_adder",
                    "rules": [
                        {
                            "filter": "*",
                            "generic_adder": {"add": {"event.tags": "generic added tag"}},
                        }
                    ],
                }
            }
        ),
        Factory.create(
            {
                "pseudo_this": {
                    "type": "ng_pseudonymizer",
                    "pubkey_analyst": "examples/exampledata/rules/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "examples/exampledata/rules/pseudonymizer/example_depseudo_pub.pem",
                    "regex_mapping": "examples/exampledata/rules/pseudonymizer/regex_mapping.yml",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "outputs": [{"kafka": "pseudonyms"}],
                    "rules": [
                        {
                            "filter": "user.name",
                            "pseudonymizer": {
                                "id": "pseudonymizer-1a3c69b2-5d54-4b6b-ab07-c7ddbea7917c",
                                "mapping": {"user.name": "RE_WHOLE_FIELD"},
                            },
                        }
                    ],
                    "max_cached_pseudonyms": 1000000,
                }
            }
        ),
    ]
    for processor in processors:
        await processor.setup()
    return processors


@pytest.fixture(name="opensearch_output")
def get_opensearch_mock():
    return Factory.create(
        {
            "opensearch": {
                "type": "ng_dummy_output",
            }
        }
    )


@pytest.fixture(name="kafka_output")
def get_kafka_mock():
    return Factory.create(
        {
            "kafka": {
                "type": "ng_dummy_output",
                "default": False,
            }
        }
    )


@pytest.fixture(name="default_output")
def get_default_output(opensearch_output):
    return opensearch_output


@pytest.fixture(name="named_outputs")
def get_named_outputs(opensearch_output, kafka_output):
    return {"opensearch": opensearch_output, "kafka": kafka_output}


@pytest.fixture(name="error_output")
def get_error_output_mock() -> DummyOutput:
    return typing.cast(
        DummyOutput,
        Factory.create(
            {
                "error": {
                    "type": "ng_dummy_output",
                }
            }
        ),
    )


class TestWorkflow:
    """Test the workflow"""

    @staticmethod
    @pytest.fixture
    async def run_workflow(
        dummy_input: DummyInput,
        processors: Sequence[Processor],
        default_output: Output,
        named_outputs: dict[str, Output],
        error_output: Output,
    ) -> AsyncGenerator:
        """
        This fixture provides a helper method for running an exhaustive orchestration workflow.
        The workflow runs until all input docs where read and starts a graceful shutdown after that.
        Per default, the standard fixtures (see parameters) are used to configure the orchestrator.
        Behavior can be modified by modifying the fixture or passing replacements to the helper.
        """

        components: set[Component] = set()

        async def run(
            dummy_input: DummyInput = dummy_input,
            processors: Sequence[Processor] = processors,
            default_output: Output = default_output,
            named_outputs: dict[str, Output] = named_outputs,
            error_output: Output = error_output,
        ):
            assert not components, "run() should only be executed once"
            components.update(
                {
                    dummy_input,
                    *processors,
                    default_output,
                    *named_outputs.values(),
                    error_output,
                }
            )

            orchestrator = create_orchestrator(
                dummy_input,
                processors,
                default_output=default_output,
                error_output=error_output,
                named_outputs=named_outputs,
            )

            await asyncio.gather(*(component.setup() for component in components))

            await asyncio.wait_for(
                # start graceful shutdown when input is exhausted
                orchestrator.run(dummy_input.empty_event, graceful_shutdown_timeout_s=0.5),
                timeout=1,
            )

        yield run

        assert components, "run(...) should have been used and thus components should be populated"

        await asyncio.gather(*(component.shut_down() for component in components))

    async def test_event_flow_to_outputs_and_acknowledge(
        self, run_workflow, default_output, named_outputs, error_output, dummy_input
    ) -> None:
        await run_workflow()

        assert len(default_output.events) == 3, "3 log events sent"
        assert len(named_outputs["kafka"].events) == 1, "1 extra data event"
        assert len(error_output.events) == 0, "no errors"
        assert len(dummy_input.acknowledged_events) == 3, "3 log events acknowledged"

    async def test_processor_failure_to_error_output(
        self, run_workflow, default_output, named_outputs, error_output, dummy_input, processors
    ) -> None:

        with mock.patch.object(processors[0], "_apply_rules") as processor_apply_rules:
            processor_apply_rules.side_effect = Exception("Processing error")

            await run_workflow()

        assert len(default_output.events) == 0, "no regular output expected"
        assert len(named_outputs["kafka"].events) == 0, "no extra events expected"
        assert len(error_output.events) == 3, "no errors"
        assert len(dummy_input.acknowledged_events) == 3, "3 log events acknowledged"

    async def test_default_output_failure_to_error_output(
        self, run_workflow, default_output: DummyOutput, named_outputs, error_output, dummy_input
    ) -> None:
        default_output.exceptions = ["first event fails to send"]

        await run_workflow()

        assert len(default_output.events) == 2, "2/3 events were stored"
        assert is_sequence_of(default_output.events, LogEvent)
        assert len(named_outputs["kafka"].events) == 1, "the 3rd event had an extra event"
        assert len(error_output.events) == 1, "the 1st event failed and was routed to error"
        assert is_sequence_of(error_output.events, ErrorEvent)
        assert len(dummy_input.acknowledged_events) == 3, "3 log events acknowledged"

    async def test_extra_event_targets_invalid_output(
        self, run_workflow, default_output: DummyOutput, error_output, dummy_input
    ) -> None:

        await run_workflow(named_outputs={})

        assert len(default_output.events) == 2, "2/3 events were stored"
        assert is_sequence_of(default_output.events, LogEvent)
        assert len(error_output.events) == 1, "the 1st event failed and was routed to error"
        assert is_sequence_of(error_output.events, ErrorEvent)
        assert len(dummy_input.acknowledged_events) == 3, "3 log events acknowledged"

    async def test_error_output_failure_critical(
        self, run_workflow, default_output, error_output
    ) -> None:
        default_output.exceptions = ["first event fails to send"]
        error_output.exceptions = ["first event fails to send"]

        with pytest.RaisesGroup(
            pytest.RaisesExc(RuntimeError, match="error output failed to send event")
        ):
            await run_workflow()
