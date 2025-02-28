# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import logging
from pathlib import Path
from unittest import mock

import pytest

from logprep.generator.http.input2 import FileLoader


class TestFileLoader:
    def setup_method(self):
        self.input_root_path = Path("test_dir/")
        self.config = {"events": 10}
        self.event_class_dir = Path("test_event_dir/")

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

    def test_retrieve_log_files(self):
        file_loader = FileLoader(self.input_root_path, **self.config)

        mock_log_class = mock.MagicMock()
        with (
            mock.patch(
                "logprep.generator.http.input2.FileLoader._load_event_class_config",
                return_value=mock_log_class,
            ),
        ):
            test_file_paths, _ = file_loader.retrieve_log_files(self.event_class_dir)
            # assert file_loader._load_event_class_config.called_once()
            assert test_file_paths == [
                Path("test_dir/test_event_dir/file1.jsonl"),
                Path("test_dir/test_event_dir/file2.jsonl"),
            ]

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="target_path: mock_target")
    @mock.patch(
        "logprep.generator.http.input2.yaml.load", return_value={"target_path": "mock_target"}
    )
    def test_load_event_class_config(self, mock_yaml_load, mock_open, caplog):
        caplog.set_level(logging.DEBUG)
        file_loader = FileLoader(self.input_root_path, **self.config)
        config = file_loader._load_event_class_config(Path("/mock/root/event_class"))
        assert config.target_path == "mock_target"
        mock_open.assert_called_once_with(
            Path("/mock/root/event_class/config.yaml"), "r", encoding="utf8"
        )
        mock_yaml_load.assert_called_once()
        assert "Following class config was loaded" in caplog.text

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="target_path: mock_target")
    @mock.patch(
        "logprep.generator.http.input2.yaml.load", return_value={"target_path": "test_target,"}
    )
    def test_load_event_class_raises_value_error(self, _mock_yaml_load, _mock_open):
        file_loader = FileLoader(self.input_root_path, **self.config)
        with pytest.raises(ValueError):
            file_loader._load_event_class_config(Path("test_dir"))
