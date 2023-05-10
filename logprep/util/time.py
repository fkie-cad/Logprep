"""logprep time helpers module"""
from datetime import datetime
from typing import Union
from zoneinfo import ZoneInfo

import ciso8601

UTC = ZoneInfo("UTC")


class TimeParserException(Exception):
    """exception class for time parsing"""


class TimeParser:
    """encapsulation of time related methods"""

    @classmethod
    def from_string(cls, source: str) -> datetime:
        """parses input string to datetime object

        Parameters
        ----------
        source : str
            input string

        Returns
        -------
        datetime
            datetime object
        """
        try:
            time_object = ciso8601.parse_datetime(source)  # pylint: disable=c-extension-no-member
            time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @classmethod
    def from_timestamp(cls, timestamp: Union[int, float]) -> datetime:
        """get datetime from unix timestamp

        Parameters
        ----------
        timestamp : int
            unit timestamp

        Returns
        -------
        datetime
            datetime object
        """
        time_object = datetime.utcfromtimestamp(timestamp)
        time_object = cls._set_utc_if_timezone_is_missing(time_object)
        return time_object

    @classmethod
    def now(cls) -> datetime:
        """returns the current time

        Returns
        -------
        datetime
            current date and time as datetime
        """
        time_object = datetime.now()
        time_object = cls._set_utc_if_timezone_is_missing(time_object)
        return time_object

    @classmethod
    def from_format(cls, source: str, format_str: str) -> datetime:
        """parse date from format

        Parameters
        ----------
        source : str
            the date string
        format_str : str
            the format string

        Returns
        -------
        datetime
            the datetime object

        Raises
        ------
        TimeParserException
            raised if something could not be parsed
        """
        try:
            time_object = datetime.strptime(source, format_str)
            time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @classmethod
    def _set_utc_if_timezone_is_missing(cls, time_object):
        if time_object.tzinfo is None:
            time_object = time_object.replace(tzinfo=UTC)
        return time_object
