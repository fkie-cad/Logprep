# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import logging
import os
import signal
from unittest import mock

import responses

from logprep.generator.controller import Controller
from logprep.generator.factory import ControllerFactory
from tests.unit.generator.http.util import create_test_event_files


@mock.patch.object(ControllerFactory, "get_loghandler", new=mock.MagicMock())
class TestController:
    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.batch_size = 10
        input_connector = mock.MagicMock()
        output_connector = mock.MagicMock()
        loghandler = mock.MagicMock()

        self.sender = mock.MagicMock()

        config = {
            "target_url": "https://testdomain.de",
        }
        self.controller = Controller(output_connector, input_connector, loghandler, **config)
        self.controller.sender = self.sender

    def test_run_calls_setup(self):
        self.controller.setup = mock.Mock()
        self.controller.run()
        self.controller.setup.assert_called_once()
        self.controller.sender.send_batches.assert_called_once()
        self.controller.input.clean_up_tempdir.assert_called_once()

    @mock.patch("threading.active_count", return_value=5)
    @mock.patch("signal.signal")
    def test_setup_calls_function(self, mock_signal, mock_active_count):

        self.controller.loghandler = mock.MagicMock()
        self.controller.output = mock.MagicMock()
        self.controller.input = mock.MagicMock()
        self.controller.input.target_sets = "some_target_sets"

        self.controller.setup()
        self.controller.loghandler.start.assert_called_once()
        mock_signal.assert_any_call(signal.SIGTERM, self.controller.stop)
        mock_signal.assert_any_call(signal.SIGINT, self.controller.stop)
        mock_active_count.assert_called_once()

    @mock.patch("threading.active_count", return_value=5)
    def test_setup_debug_output(self, mock_active_count, caplog):
        caplog.set_level(logging.DEBUG)

        self.controller.loghandler = mock.MagicMock()
        self.controller.output = mock.MagicMock()
        self.controller.input = mock.MagicMock()
        self.controller.input.target_sets = "some_target_sets"

        self.controller.setup()
        assert "Start thread Fileloader active threads" in caplog.text
        assert int(caplog.messages[0][-1]) == mock_active_count.return_value

    @mock.patch("time.perf_counter")
    def test_run_measures_time(self, mock_perf_counter):
        self.controller.run()
        mock_perf_counter.assert_called()
        assert mock_perf_counter.call_count == 2

    @mock.patch("logprep.generator.controller.logger")
    def test_run_duration_is_positive(self, mock_logger):
        self.controller.run()
        mock_logger.info.assert_called()
        run_duration = mock_logger.info.call_args_list[-1].args[1]
        assert run_duration > 0

    @responses.activate
    def test_run(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        class_one_number_events = 100
        class_one_config = {
            "target_path": "/target-one",
            "timestamps": [{"key": "source.field", "format": "%Y%M%d"}],
        }
        create_test_event_files(
            dataset_path,
            {"example": "event"},
            class_one_number_events,
            class_name="class_one",
            config=class_one_config,
        )
        class_two_number_events = 100
        class_two_config = {
            "target_path": "/target-two",
            "timestamps": [{"key": "source.field", "format": "%H%M%S"}],
        }
        create_test_event_files(
            dataset_path,
            {"example": "event"},
            class_two_number_events,
            class_name="class_two",
            config=class_two_config,
        )
        self.controller.input.input_root_path = dataset_path
        self.controller.input.temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.controller.input.temp_dir, exist_ok=True)
        expected_status_code = 200
        responses.add(responses.POST, f"{self.target_url}/target-one", status=expected_status_code)
        responses.add(responses.POST, f"{self.target_url}/target-two", status=expected_status_code)
        self.controller.run()

        for call_id, call in enumerate(responses.calls):
            if call_id < (class_one_number_events / self.batch_size):
                assert (
                    call.request.url == f"{self.target_url}/target-one"
                ), f"Call {call_id} has wrong target"
            else:
                assert (
                    call.request.url == f"{self.target_url}/target-two"
                ), f"Call {call_id} has wrong target"
            expected_http_header = "application/x-ndjson; charset=utf-8"
            assert call.request.headers.get("Content-Type") == expected_http_header
            assert call.response.status_code == 200
