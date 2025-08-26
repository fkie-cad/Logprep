# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import pytest

from logprep.ng.runner import Runner
from logprep.util.configuration import Configuration


@pytest.fixture(name="configuration")
def get_logprep_config() -> Configuration:
    return Configuration()


class TestRunner:
    def setup_method(self):
        self.runner = Runner()

    def test_runner_initializes(self):
        assert self.runner is not None
