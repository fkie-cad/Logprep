# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import logging
from pathlib import Path
from unittest import mock

import msgspec
import pytest

from logprep.generator.input import EventClassConfig, FileLoader, FileWriter, Input
from logprep.generator.manipulator import Manipulator


class TestInput:

    def setup_method(self):
        self.config = {"events": 10, "input_dir": "test_dir"}
        self.event_class_dir = Path("test_event_dir/")
        self.input = Input(self.config)
        self.mock_isdir = mock.patch("pathlib.Path.is_dir", return_value=True)
        self.mock_exists = mock.patch("pathlib.Path.exists", return_value=True)
        self.mock_iterdir = mock.patch("pathlib.Path.iterdir", return_value=[Path("test_dir")])

        self.mock_isdir.start()
        self.mock_exists.start()

    def teardown_method(self):
        mock.patch.stopall()

    def test_init(self):
        assert self.input.input_root_path == Path(self.config["input_dir"])
        assert isinstance(self.input.file_loader, FileLoader)
        assert isinstance(self.input.file_writer, FileWriter)
        assert self.input.config == self.config
        assert self.input.number_events_of_dataset == 0

    def test_decoder_encoder_property(self):
        assert isinstance(self.input._encoder, msgspec.json.Encoder)
        assert isinstance(self.input._decoder, msgspec.json.Decoder)

    def test_temp_filename_prefix_property(self):
        assert self.input._temp_filename_prefix == "logprep_input_data"

    @mock.patch("logprep.generator.input.Path.iterdir", return_value=[Path("test_dir")])
    @mock.patch(
        "logprep.generator.input.FileLoader.retrieve_log_files",
        return_value=(mock.MagicMock, mock.MagicMock),
    )
    @mock.patch("logprep.generator.input.Input._set_manipulator")
    @mock.patch("logprep.generator.input.Input._populate_events_list")
    def test_reformat_dataset(
        self, mock_iterdir, mock_retrieve_log_files, mock_set_manipulator, mock_populate_events_list
    ):
        self.input.reformat_dataset()
        mock_retrieve_log_files.assert_called()
        mock_retrieve_log_files.mock_set_manipulator()
        mock_retrieve_log_files.mock_populate_event_list()

    @mock.patch("logprep.generator.input.logger")
    @mock.patch("logprep.generator.input.Path.iterdir", return_value=[])
    def test_reformat_dataset_returns_positive_time(self, mock_iterdir, mock_logger):
        self.input.reformat_dataset()
        mock_logger.info.assert_called()
        run_duration = mock_logger.info.call_args_list[-1].args[1]
        assert run_duration > 0

    @mock.patch("logprep.generator.input.FileWriter.write_events_file")
    def test_populate_events_list(self, mock_write_events_file):
        file_paths = [Path("test1.jsonl"), Path("test2.jsonl")]
        log_class_config = mock.MagicMock(target="test_target")

        with mock.patch("builtins.open", mock.mock_open(read_data='{"event": "data"}\n')):
            self.input._populate_events_list(file_paths, log_class_config)

        mock_write_events_file.assert_called()
        assert self.input.number_events_of_dataset > 0

    def test_set_manipulator(self):
        mock_log_class_config = mock.MagicMock()
        mock_log_class_config.target = "test_target"
        self.input._set_manipulator(mock_log_class_config)

        assert "test_target" in self.input.log_class_manipulator_mapping
        assert isinstance(self.input.log_class_manipulator_mapping["test_target"], Manipulator)

    @mock.patch("logprep.generator.input.FileWriter.write_events_file")
    def test_populate_events_list_full(self, mock_write_events_file):
        file_paths = [Path("test1.jsonl"), Path("test2.jsonl")]
        log_class_config = mock.MagicMock(target="test_target")
        self.input.MAX_EVENTS_PER_FILE = 2
        with mock.patch("builtins.open", mock.mock_open(read_data='{"event": "data"}\n')):
            self.input._populate_events_list(file_paths, log_class_config)

        mock_write_events_file.assert_called()
        assert self.input.number_events_of_dataset > 0

    @mock.patch("shutil.rmtree")
    def test_clean_up_tempdir(self, mock_rmtree, caplog):
        with (
            mock.patch.object(Path, "exists", return_value=True),
            mock.patch.object(Path, "is_dir", return_value=True),
        ):
            with caplog.at_level("INFO"):
                self.input.clean_up_tempdir()
        mock_rmtree.assert_called_with(self.input.temp_dir)
        assert "Cleaned up temp dir:" in caplog.text


class TestFileLoader:
    def setup_method(self):
        self.input_root_path = Path("test_dir/")
        self.config = {"events": 10}
        self.event_class_dir = Path("test_event_dir/")
        self.mock_iterdir = mock.patch(
            "logprep.generator.input.Path.iterdir", return_value=[Path("test_dir")]
        )

        self.mock_listdir = mock.patch(
            "pathlib.Path.glob", return_value=["file1.jsonl", "file2.jsonl"]
        )
        self.mock_isdir = mock.patch("pathlib.Path.is_dir", return_value=True)
        self.mock_exists = mock.patch("pathlib.Path.exists", return_value=True)

        self.mock_listdir.start()
        self.mock_isdir.start()
        self.mock_exists.start()

    def teardown_method(self):
        mock.patch.stopall()

    def test_init_set_values(self):
        file_loader = FileLoader(self.input_root_path, **self.config)
        assert file_loader.input_root_path is self.input_root_path
        assert file_loader.number_events_of_dataset == self.config["events"]

    @mock.patch(
        "logprep.generator.input.Path.iterdir",
        return_value=[
            Path("test_dir/test_event_dir/file1.jsonl"),
            Path("test_dir/test_event_dir/file2.jsonl"),
        ],
    )
    def test_retrieve_log_files(self, mock_iter_dir):
        file_loader = FileLoader(self.input_root_path, **self.config)

        mock_log_class = mock.MagicMock()
        with (
            mock.patch(
                "logprep.generator.input.FileLoader._load_event_class_config",
                return_value=mock_log_class,
            ),
        ):
            test_file_paths, _ = file_loader.retrieve_log_files(self.event_class_dir)
            # assert file_loader._load_event_class_config.called_once()
            assert test_file_paths == [
                Path("test_dir/test_event_dir/file1.jsonl"),
                Path("test_dir/test_event_dir/file2.jsonl"),
            ]

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="target: mock_target")
    @mock.patch("logprep.generator.input.yaml.load", return_value={"target": "mock_target"})
    def test_load_event_class_config(self, mock_yaml_load, mock_open, caplog):
        caplog.set_level(logging.DEBUG)
        file_loader = FileLoader(self.input_root_path, **self.config)
        config = file_loader._load_event_class_config(Path("/mock/root/event_class"))
        assert config.target == "mock_target"
        mock_open.assert_called_once_with(
            Path("/mock/root/event_class/config.yaml"), "r", encoding="utf8"
        )
        mock_yaml_load.assert_called_once()
        assert "Following class config was loaded" in caplog.text

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="target: mock_target")
    @mock.patch("logprep.generator.input.yaml.load", return_value={"target": "test_target,"})
    def test_load_event_class_raises_value_error(self, _mock_yaml_load, _mock_open):
        file_loader = FileLoader(self.input_root_path, **self.config)
        with pytest.raises(ValueError):
            file_loader._load_event_class_config(Path("test_dir"))


def test_write_events_file_no_shuffle():
    test_events = ["event1", "event2", "event3"]
    test_dir = Path("test_dir")
    config = {"shuffle": False}
    file_writer = FileWriter()

    with mock.patch("builtins.open", new_callable=mock.MagicMock) as mock_open:
        file_writer.write_events_file(test_events, test_dir, config)

        mock_open.assert_called_once_with(
            test_dir / "logprep_input_data_0000.txt", "a", encoding="utf8"
        )
        mock_open.return_value.__enter__.return_value.writelines.assert_called_once()

    assert test_events == []
    assert file_writer.event_file_counter == 1


def test_target_and_target_path_none():
    """Test that ValueError is raised when both 'target' and 'target_path' are None."""
    with pytest.raises(ValueError, match="Either 'target' or 'target_path' must be provided."):
        EventClassConfig()


def test_target_path_deprecation_warning():
    with pytest.warns(
        DeprecationWarning,
        match="'target_path' is deprecated and will be removed in the future. "
        "Use 'target' instead.",
    ):
        config = EventClassConfig(target_path="old_path")

    assert config.target == "old_path", "Expected 'target' to be set from 'target_path'"
