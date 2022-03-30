import numpy as np

from logprep.util.processor_stats import ProcessorStats, StatsClassesController


def assert_avg_processing_time_calculation(processor_stats, time_samples):
    # update average step by step and compare to the total average of the values until then
    for i, time_sample in enumerate(time_samples):
        processor_stats.update_average_processing_time(time_sample)

        real_mean = np.mean(time_samples[:i + 1])
        assert real_mean == processor_stats.aggr_data.get("avg_processing_time")


class TestProcessorStats:
    StatsClassesController.ENABLED = True

    def test_correct_calculation_of_avg_processing_time(self):
        processor_stats = ProcessorStats()

        # define a set of samples
        time_samples = [4, 21, 5, 48, 12, 1, 3, 54, 3, 3]
        assert_avg_processing_time_calculation(processor_stats, time_samples)

    def test_correct_calculation_of_avg_processing_time_with_reset_in_between(self):
        processor_stats = ProcessorStats()

        # define a set of samples
        first_time_samples = [4, 21, 5, 48, 12, 1, 3, 54, 3, 3]
        assert_avg_processing_time_calculation(processor_stats, first_time_samples)

        processor_stats.reset_statistics()

        second_time_samples = [5, 7, 15, 3, 18]
        assert_avg_processing_time_calculation(processor_stats, second_time_samples)
