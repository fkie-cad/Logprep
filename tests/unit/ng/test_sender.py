# pylint: disable=missing-docstring
# pylint: disable=protected-access
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.error_event import ErrorEvent
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.sre_event import SreEvent
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender


@pytest.fixture(name="input_connector")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"message": "Log message 2"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"user": {"name": "John Doe"}}, original=b"", state=EventStateType.RECEIVED),
        ]
    )


@pytest.fixture(name="processors")
def get_processors_mock():
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
        processor.setup()
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


@pytest.fixture(name="error_output")
def get_error_output_mock():
    return Factory.create(
        {
            "error": {
                "type": "ng_dummy_output",
            }
        }
    )


@pytest.fixture(name="pipeline")
def get_pipeline_mock(input_connector, processors):
    """Create a mock for the Pipeline class."""
    return Pipeline(input_connector, processors)


class TestSender:
    """Test the Sender class."""

    def test_sender_initialization(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        assert isinstance(sender.pipeline, Pipeline)
        assert sender._outputs == {opensearch_output.name: opensearch_output}
        assert sender._error_output is None
        assert sender._default_output == opensearch_output, "Default output should be the first one"
        assert sender.should_exit is False

    def test_sender_sends_events_and_extra_data_to_output(
        self, pipeline, opensearch_output, kafka_output
    ):
        sender = Sender(
            pipeline=pipeline, outputs=[opensearch_output, kafka_output], error_output=None
        )
        sender.stop()

        list(sender)

        assert len(opensearch_output.events) == 3, "3 log events "
        assert len(kafka_output.events) == 1, "1 extra data event"
        assert all(event.state == EventStateType.DELIVERED for event in opensearch_output.events)
        assert all(event.state == EventStateType.DELIVERED for event in kafka_output.events)

    def test_sender_sends_failed_events_to_error_output(
        self, pipeline, opensearch_output, error_output, kafka_output
    ):
        sender = Sender(
            pipeline=pipeline, outputs=[opensearch_output, kafka_output], error_output=error_output
        )

        try:
            with mock.patch.object(pipeline.processors[0], "_apply_rules") as mock_process:
                mock_process.side_effect = Exception("Processing error")

                sender.stop()
                list(sender)

                assert len(opensearch_output.events) == 0, "no events delivered"
                assert len(error_output.events) == 3, "3 failed events sent to error output"
                assert all(isinstance(event, ErrorEvent) for event in error_output.events)
        except AttributeError:
            pass

    def test_raises_value_error_for_invalid_output(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        event = LogEvent({"message": "Test message"}, original=b"", state=EventStateType.RECEIVED)
        event.extra_data.append(SreEvent({"test": "data"}, outputs=[{"invalid_output": "target"}]))
        with pytest.raises(ValueError, match="Output invalid_output not configured."):
            sender._send_processed(event)

    def test_iter_handles_errors_during_sending_to_error_output(
        self, opensearch_output, error_output, caplog
    ):
        caplog.set_level("ERROR")
        event = LogEvent({"message": "Test message"}, original=b"", state=EventStateType.FAILED)
        sender = Sender(
            pipeline=iter([event]),
            outputs=[opensearch_output],
            error_output=error_output,
        )
        error_event = sender._get_error_event(event)

        def mock_store_side_effect(*_) -> None:
            error_event.state.next_state(success=True)  # stored_in_error_output

        def mock_flush_side_effect(*_) -> None:
            error_event.state.next_state(success=False)  # failed

        with mock.patch.object(sender, "_get_error_event", return_value=error_event):
            with mock.patch.object(sender._error_output, "store") as mock_store:
                mock_store.side_effect = mock_store_side_effect
                with mock.patch.object(sender._error_output, "flush") as mock_flush:
                    mock_flush.side_effect = mock_flush_side_effect
                    next(iter(sender))
        assert "Error during sending to error output" in caplog.text
        assert "ErrorEvent" in caplog.text
        assert "state=failed" in caplog.text
        assert '{"message": "Test message"}' in caplog.text

    def test_get_error_event(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        event = LogEvent(
            {"message": "Test message"}, original=b"the event", state=EventStateType.FAILED
        )
        error_event = sender._get_error_event(event)
        assert isinstance(error_event, ErrorEvent)
        assert error_event.data["@timestamp"] is not None
        assert error_event.data["reason"] == "Unknown error"
        assert error_event.data["original"] == "the event"
        assert error_event.state.current_state == EventStateType.PROCESSED

    def test_get_error_event_with_error_list(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        event = LogEvent(
            {"message": "Test message"}, original=b"the event", state=EventStateType.FAILED
        )
        event.errors.append(ValueError("Error 1"))
        event.errors.append(TypeError("Error 2"))
        error_event = sender._get_error_event(event)
        assert isinstance(error_event, ErrorEvent)
        assert error_event.data["@timestamp"] is not None
        assert (
            error_event.data["reason"]
            == "Error during processing: (ValueError('Error 1'), TypeError('Error 2'))"
        )
        assert error_event.data["original"] == "the event"
        assert error_event.state.current_state == EventStateType.PROCESSED

    def test_sender_next_raises_not_implemented_error(self):
        output_mock = mock.MagicMock()
        sender = Sender(
            pipeline=iter([]), outputs=[output_mock], error_output=None, process_count=623
        )

        with pytest.raises(NotImplementedError):
            next(sender)

    def test_send_and_flush_failed_events_early_exiting_with_empty_error_list(self):
        output_mock = mock.MagicMock()
        sender = Sender(
            pipeline=iter([]), outputs=[output_mock], error_output=None, process_count=623
        )

        sender._send_and_flush_failed_events(batch_events=[])

    def test_sender_sets_message_backlog_size(self):
        output_mock = mock.MagicMock()
        sender = Sender(
            pipeline=iter([]), outputs=[output_mock], error_output=None, process_count=623
        )
        assert sender.batch_size == 623

    def test_sender_respects_process_count(self):
        output_mock = mock.MagicMock()
        sender = Sender(
            pipeline=iter(
                [
                    LogEvent(
                        {"message": f"Log message {i}"}, original=b"", state=EventStateType.RECEIVED
                    )
                    for i in range(6666)
                ]
            ),
            outputs=[output_mock],
            error_output=None,
            process_count=666,
        )
        mock_batch_lengths = None

        def mock_send_and_flush_side_effect(batch_events):
            nonlocal mock_batch_lengths
            mock_batch_lengths = len(batch_events)
            raise Exception("Stop iteration for test")

        with mock.patch.object(sender, "_send_and_flush_processed_events") as mock_send_and_flush:
            mock_send_and_flush.side_effect = mock_send_and_flush_side_effect

            with pytest.raises(Exception, match="Stop iteration for test"):
                list(sender)

        assert mock_batch_lengths == 666

    def test_sender_respects_process_count_even_if_stopped(self):
        output_mock = mock.MagicMock()
        sender = Sender(
            pipeline=iter(
                [
                    LogEvent(
                        {"message": f"Log message {i}"}, original=b"", state=EventStateType.RECEIVED
                    )
                    for i in range(6666)
                ]
            ),
            outputs=[output_mock],
            error_output=None,
            process_count=666,
        )
        mock_batch_lengths = None

        def mock_send_and_flush_side_effect(batch_events):
            nonlocal mock_batch_lengths
            mock_batch_lengths = len(batch_events)
            raise Exception("Stop iteration for test")

        with mock.patch.object(sender, "_send_and_flush_processed_events") as mock_send_and_flush:
            mock_send_and_flush.side_effect = mock_send_and_flush_side_effect

            with pytest.raises(Exception, match="Stop iteration for test"):
                sender.stop()
                list(sender)

        assert mock_batch_lengths == 666

    def test_sender_handles_failed_extra_data(self, pipeline, opensearch_output, error_output):
        sre_event = SreEvent({"sre": "data"}, outputs=[{"opensearch": "sre_topic"}])
        sre_event.state.current_state = EventStateType.FAILED

        log_event = LogEvent(
            data={"message": "Test message"}, original=b"the event", state=EventStateType.PROCESSED
        )
        log_event.extra_data.append(sre_event)
        log_event.errors.append(ValueError("Failed SRE Event"))

        input_iterator = iter([log_event])

        with mock.patch.object(pipeline, "log_events_iter", new=input_iterator):
            sender = Sender(
                pipeline=pipeline, outputs=[opensearch_output], error_output=error_output
            )

            with mock.patch.object(sender, "_send_extra_data"):
                sender.stop()
                list(sender)

            assert log_event.state == EventStateType.FAILED
            error_event = error_output.events[0]
            assert isinstance(error_event, ErrorEvent)
            assert error_event.state == EventStateType.DELIVERED

    def test_setup_calls_output_setup(self, opensearch_output, pipeline):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        with mock.patch.object(opensearch_output, "setup") as mock_setup:
            sender.setup()
        mock_setup.assert_called_once()

    def test_setup_calls_pipeline_setup(self, opensearch_output, pipeline):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        with mock.patch.object(pipeline, "setup") as mock_setup:
            sender.setup()
        mock_setup.assert_called_once()

    def test_setup_calls_error_output_setup(self, opensearch_output, pipeline, error_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=error_output)
        with mock.patch.object(error_output, "setup") as mock_setup:
            sender.setup()
        mock_setup.assert_called_once()

    def test_shut_down_calls_output_shut_down(self, opensearch_output, pipeline):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        with mock.patch.object(opensearch_output, "shut_down") as mock_shut_down:
            sender.shut_down()
        mock_shut_down.assert_called_once()

    def test_shut_down_calls_pipeline_shut_down(self, opensearch_output, pipeline):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        with mock.patch.object(pipeline, "shut_down") as mock_shut_down:
            sender.shut_down()
        mock_shut_down.assert_called_once()

    def test_shut_down_calls_error_output_shut_down(
        self, opensearch_output, pipeline, error_output
    ):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=error_output)
        with mock.patch.object(error_output, "shut_down") as mock_shut_down:
            sender.shut_down()
        mock_shut_down.assert_called_once()
