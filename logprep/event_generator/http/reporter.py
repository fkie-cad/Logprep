"""This module tracks statistics and creates a final report for the generator"""
import datetime
import logging
import os
from functools import cached_property, reduce
from pathlib import Path
from string import Template

import pandas as pd
import yaml


class Reporter:
    """The Reporter collects statistics and returns a final markdown report"""

    EXPERIMENT_ROOT_DIR = Path("experiments")
    REPORT_TEMPLATE = Template(
        """# Test Run From $timestamp

## Used arguments

```yaml
$arguments
```

## Statistics

### Mean statistic per second

The raw data was cumulated by seconds and then a total mean was calculated

$mean_per_second

### Total numbers

$totals

### Mean batch send time

The mean batch send time was: $mean_batch_send_time

### Run Duration

The execution duration took: $run_duration
"""
    )

    @cached_property
    def experiment_dir(self):
        """Directory where the statistics and the report will be written to"""
        self.experiment_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        experiment_dir = self.EXPERIMENT_ROOT_DIR / self.experiment_timestamp
        os.makedirs(experiment_dir)
        return experiment_dir

    def __init__(self, args: dict):
        self.arguments = self._prepare_arguments_for_export(args.copy())
        self.experiment_timestamp = None
        self.data = pd.DataFrame()
        self.run_duration = -1
        self.log = logging.getLogger("Reporter")

    def _prepare_arguments_for_export(self, args):
        """Censors credentials and removes the logger from the arguments"""
        args["password"] = "####"
        args["user"] = "####"
        return args

    def update(self, statistics: dict):
        """Update the data inside the reporter with new statistics"""
        if not statistics:
            return
        new_data = statistics.copy()
        events_stats = [new_data[stat] for stat in new_data.keys() if "Event" in stat]
        total_events_send = reduce(lambda a, b: a + b, events_stats)
        new_data["total_events_send"] = total_events_send
        request_stats = [new_data[stat] for stat in new_data.keys() if "Request" in stat]
        total_events_send = reduce(lambda a, b: a + b, request_stats)
        new_data["total_requests_send"] = total_events_send
        new_data["time"] = datetime.datetime.now()
        new_data_df = pd.DataFrame(new_data, index=[0])
        self.data["time"] = self.data.index
        self.data.reset_index(inplace=True, drop=True)
        self.data = self.data.merge(new_data_df, how="outer")
        self.data.set_index("time", inplace=True)

    def write_experiment_results(self):
        """Write at the end of the run the experiment results to hard drive"""
        self._rewrite_columns_names()
        self._write_raw_data()
        relevant_columns = self._get_relevant_column_names()
        mean_per_second = self._get_mean_per_second_metrics(relevant_columns)
        aggregate = self._aggregate_metrics(relevant_columns)
        metric_sums = self._get_sums(aggregate, relevant_columns)
        self._write_markdown_report(aggregate, mean_per_second, metric_sums)

    def _rewrite_columns_names(self):
        """In column names replace spaces with underscore and make them lower case"""
        columns = [column.replace(" ", "_").lower() for column in self.data.columns]
        self.data.columns = columns

    def _write_raw_data(self):
        """Write the raw data of the experiment run as csv file to disk"""
        target_path = self.experiment_dir / "raw_data.csv"
        self.data.sort_values(by="time")
        self.data.to_csv(target_path)
        self.log.info("Wrote raw data to: %s", os.path.abspath(target_path))

    def _get_relevant_column_names(self):
        """Returns the column names which should be used for calculating statistics"""
        request_columns = [col for col in self.data.columns if "requests" in col]
        events_columns = [col for col in self.data.columns if "events" in col]
        relevant_columns = request_columns + events_columns
        return relevant_columns

    def _get_mean_per_second_metrics(self, relevant_columns):
        """
        Calculate the mean per second statistics by taking the sum of 1 second bins and then taking
        the mean over all bins.
        """
        mean_per_second = self.data[relevant_columns].groupby(pd.Grouper(freq="1s")).sum().mean()
        mean_per_second = mean_per_second.reindex(sorted(mean_per_second.index), axis=0)
        return mean_per_second

    def _aggregate_metrics(self, relevant_columns):
        """Calculate the sum of the relevant metrics and the mean of the batch_send_time"""
        sum_aggregations = {col: ["sum"] for col in relevant_columns}
        mean_aggregation = {"batch_send_time": ["mean"]}
        aggregations = {}
        aggregations.update(sum_aggregations)
        aggregations.update(mean_aggregation)
        aggregate = self.data.agg(aggregations)
        aggregate = aggregate.reindex(sorted(aggregate.columns), axis=1)
        return aggregate

    def _get_sums(self, aggregate, relevant_columns):
        """
        Get only the sum aggregations from the relevant metrics, ignores the mean_batch_send_time
        """
        totals = aggregate.loc["sum", relevant_columns]
        totals = totals.reindex(sorted(totals.index), axis=0)
        return totals

    def _write_markdown_report(self, aggregate, mean_per_second, metric_sums):
        """Writes the actual precomputed statistics to hard drive"""
        report_md = self.REPORT_TEMPLATE.safe_substitute(
            timestamp=self.experiment_timestamp,
            arguments=yaml.dump(self.arguments),
            mean_per_second=mean_per_second.to_markdown(),
            totals=metric_sums.to_markdown(),
            mean_batch_send_time=f"{aggregate.loc['mean', 'batch_send_time']:.5f} s",
            run_duration=f"{self.run_duration:.5f} s",
        )
        report_path = self.experiment_dir / "report.md"
        with open(report_path, "w", encoding="utf8") as report_file:
            report_file.write(report_md)
        self.log.info(f"Wrote report to: {os.path.abspath(report_path)}")

    def set_run_duration(self, duration):
        self.run_duration = duration
