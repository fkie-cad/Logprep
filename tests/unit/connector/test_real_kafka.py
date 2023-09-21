# pylint: disable=missing-docstring
import os

import pytest

in_ci = os.environ.get("CI")


@pytest.mark.skipif(in_ci, reason="requires kafka")
class TestKafkaConnection:
    def test_simple(self):
        assert False