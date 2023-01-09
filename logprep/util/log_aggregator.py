"""This module implements a logger that is able to aggregate log messages."""

import logging
from logging import LogRecord, Filter
from time import time, sleep
import threading


class Aggregator(Filter):
    """Used to aggregate log messages."""

    logs = {}
    count_threshold = 4
    log_period = 10
    timer_thread = None

    @classmethod
    def setup(cls, count: int, period: float):
        """Setup aggregating logger.

        Parameters
        ----------
        count : int
            Count of log messages for which aggregation should begin.
        period : float
            Period for which log messages are being counted for aggregation.

        """
        cls.count_threshold = count
        cls.log_period = period
        cls.logs.clear()

    @classmethod
    def start_timer(cls):
        """Start repeating timer for aggregation."""
        cls.timer_thread = threading.Timer(cls.log_period, cls._log_aggregated)
        cls.timer_thread.daemon = True
        cls.timer_thread.start()

    @classmethod
    def _aggregate(cls, record: LogRecord) -> bool:
        log_id = "{0[levelname]}:{0[name]}:{0[msg]}".format(record.__dict__)
        if log_id not in cls.logs:
            cls.logs[log_id] = {
                "cnt": 1,
                "first_record": record,
                "last_record": None,
                "cnt_passed": 0,
                "aggregate": False,
            }
        else:
            cls.logs[log_id]["cnt"] += 1
            cls.logs[log_id]["last_record"] = record

            if record.created - cls.logs[log_id]["last_record"].created < cls.log_period:
                if cls.logs[log_id]["cnt"] > cls.count_threshold or cls.logs[log_id]["aggregate"]:
                    return False

        cls.logs[log_id]["aggregate"] = False
        cls.logs[log_id]["first_record"] = record
        cls.logs[log_id]["cnt_passed"] += 1

        return True

    @classmethod
    def _log_aggregated(cls):
        while True:
            cls._perform_logging_if_possible()
            sleep(cls.log_period)

    @classmethod
    def _perform_logging_if_possible(cls):
        for log_id, data in list(cls.logs.items()):
            count = data["cnt"] - data["cnt_passed"]
            if count > 1 and data["last_record"]:
                time_passed = round(time() - data["first_record"].created, 1)
                time_passed = min(time_passed, cls.log_period)
                if time_passed < 60:
                    period = f"{time_passed} sek"
                else:
                    period = f"{time_passed / 60.0:.1f} min"
                last_record = data["last_record"]
                last_record.msg = f"{last_record.msg} ({count} in ~{period})"
                logging.getLogger(last_record.name).log(last_record.levelno, last_record.msg)

                cls.logs[log_id]["first_record"] = data["last_record"]
                cls.logs[log_id]["last_record"] = None
                cls.logs[log_id]["cnt"] = 0
                cls.logs[log_id]["cnt_passed"] = 0
                cls.logs[log_id]["aggregate"] = True
            else:
                if time() - cls.logs[log_id]["first_record"].created >= cls.log_period:
                    cls.logs[log_id]["aggregate"] = False

    def filter(self, record: LogRecord) -> bool:
        """Print aggregation if it is ready via a Logger filter."""
        return Aggregator._aggregate(record)
