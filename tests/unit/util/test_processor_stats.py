import numpy as np

from logprep.util.processor_stats import ProcessorStats, StatsClassesController


class TestProcessorStats:

    def test_correct_calculation_of_avg_processing_time(self):
        StatsClassesController.ENABLED = True

        ps = ProcessorStats()

        # define a set of samples
        time_samples = [4, 21, 5, 48, 12, 1, 3, 54, 3, 3]

        # update average step by step and compare to the total average of the values until then
        for i, time_sample in enumerate(time_samples):
            ps.update_average_processing_time(time_sample)

            real_mean = np.mean(time_samples[:i + 1])
            assert real_mean, ps.aggr_data.get("avg_processing_time")
