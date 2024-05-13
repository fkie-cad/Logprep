# pylint: disable=too-few-public-methods
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
import numpy as np
import pytest
from pydantic import BaseModel

from logprep.generator.kafka.process_runner import get_record_cnt_for_process


class ConfigurationTest(BaseModel):
    count: int
    process_count: int


class TestUtil:
    @pytest.mark.parametrize("count", range(5))
    @pytest.mark.parametrize("process_count", range(1, 10))
    def test_get_record_cnt_for_two_processes(self, count, process_count):
        config = ConfigurationTest(
            **{
                "count": count,
                "process_count": process_count,
            }
        )

        results = []
        for idx in range(config.process_count):
            results.append(get_record_cnt_for_process(config, idx))
        assert np.sum(results) == config.count
        assert np.average(results) == config.count / config.process_count
