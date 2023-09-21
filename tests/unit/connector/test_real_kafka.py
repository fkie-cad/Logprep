# pylint: disable=missing-docstring
import os

import pytest

in_ci = os.environ.get("CI")


class TestKafkaConnection:
    @pytest.mark.skipif(in_ci, reason="requires kafka")
    def test_simple(self):
        assert False
