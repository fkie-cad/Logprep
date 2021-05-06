"""This module create a logger that is able to aggregate log messages."""

from logging import getLogger, CRITICAL, FATAL, ERROR, WARNING, INFO, DEBUG, NOTSET, basicConfig, Logger
from logging.handlers import SysLogHandler
from os import path

from logprep.util.log_aggregator import Aggregator

name_to_level = {
            'CRITICAL': CRITICAL,
            'FATAL': FATAL,
            'ERROR': ERROR,
            'WARN': WARNING,
            'WARNING': WARNING,
            'INFO': INFO,
            'DEBUG': DEBUG,
            'NOTSET': NOTSET,
        }


class AggregatingLogger:
    """Used to create logger that aggregates log messages."""

    logger_config = None
    level_str = None
    log_level = None

    @classmethod
    def setup(cls, config: dict):
        """Setup aggregating logger.

        Parameters
        ----------
        config : dict
            Logprep configuration

        """
        cls.logger_config = config.get('logger', dict())

        cls.level_str = cls.logger_config.get('level', 'INFO')

        cls.log_level = name_to_level.get(cls.level_str.upper(), INFO)
        basicConfig(level=cls.log_level, format='%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s')

        Aggregator.count_threshold = cls.logger_config.get('aggregation_threshold', 4)
        Aggregator.log_period = cls.logger_config.get('aggregation_period', 30)
        Aggregator.start_timer()

    @classmethod
    def create(cls, name: str) -> Logger:
        """Create aggregating logger.

        Parameters
        ----------
        name : str
            Name for aggregating logger.

        Returns
        -------
        logger : logging.Logger
            Logger with aggregating filter

        """
        logger = getLogger(name)

        if path.exists('/dev/log'):
            logger.handlers = []
            logger.addHandler(SysLogHandler(address='/dev/log'))

        if cls.level_str.upper() not in name_to_level.keys():
            logger.info("Invalid log level '{}', defaulting to 'INFO'".format(cls.level_str.upper()))
        else:
            logger.setLevel(cls.log_level)
            logger.info("Log level set to '{}'".format(cls.level_str.upper()))

        logger.addFilter(Aggregator)

        return logger
