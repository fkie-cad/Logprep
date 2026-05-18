# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=line-too-long

import asyncio
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.pseudonym_event import PseudonymEvent
from logprep.ng.processor import process


@pytest.fixture(name="input_events")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b""),
            LogEvent({"message": "Log message 2"}, original=b""),
            LogEvent({"user": {"name": "John Doe"}}, original=b""),
        ]
    )


@pytest.fixture(name="processors", scope="session")
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
                    "outputs": [{"opensearch": "pseudonyms"}],
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


class TestProcessing:
    async def test_process_pipeline_success(self, input_events, processors):
        processed_events = await asyncio.gather(
            *(process(event, processors) for event in input_events)
        )

        for event in processed_events:
            assert isinstance(event, LogEvent)
            assert not event.errors
            assert "generic added tag" in event.get_dotted_field_value("event.tags")

    async def test_process_pipeline_failure(self, input_events, processors):
        with mock.patch.object(
            processors[0], "_apply_rules", side_effect=[None, Exception("Processing error")]
        ):
            processed_events = await asyncio.gather(
                *(process(event, processors) for event in input_events)
            )

        assert len(processed_events[0].errors) == 0
        assert len(processed_events[1].errors) == 1

    async def test_process_pipeline_generates_extra_data(self, input_events, processors):
        processed_events = await asyncio.gather(
            *(process(event, processors) for event in input_events)
        )

        for event in processed_events:
            assert isinstance(event, LogEvent)
            assert not event.errors
        assert len(processed_events[2].extra_data) == 1
        extra_data_event = processed_events[2].extra_data[0]
        assert isinstance(extra_data_event, PseudonymEvent)

    async def test_process_pipeline_empty_input(self, processors):
        input_events = iter([])
        processed_events = await asyncio.gather(
            *(process(event, processors) for event in input_events)
        )
        assert not processed_events

    async def test_empty_documents_are_not_forwarded_to_other_processors(
        self, input_events, processors
    ):
        with mock.patch.object(
            processors[0], "process", side_effect=lambda event: event.data.clear()
        ):
            with mock.patch.object(processors[1], "process"):
                processed_events = await asyncio.gather(
                    *(process(event, processors) for event in input_events)
                )
                assert len(processed_events) == 3
                assert processed_events[0].data == {}
                assert processors[0].process.call_count == 3
                assert processors[1].process.call_count == 0
