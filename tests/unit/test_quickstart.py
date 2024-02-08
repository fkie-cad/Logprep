from unittest import mock

import pytest

from logprep import run_logprep


class TestQuickstart:
    QUICKSTART_CONFIG_PATH = "quickstart/exampledata/config/pipeline.yml"

    @mock.patch("os.environ", new={"PROMETHEUS_MULTIPROC_DIR": "/tmp"})
    def test_quickstart_setup_is_valid(self):
        """ensures the quickstart rules are valid"""
        with mock.patch(
            "sys.argv",
            [
                "logprep",
                "test",
                "config",
                self.QUICKSTART_CONFIG_PATH,
            ],
        ):
            with pytest.raises(SystemExit) as e_info:
                run_logprep.cli()
        assert e_info.value.code == 0
