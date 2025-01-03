"""logprep time helpers module"""

from datetime import datetime, tzinfo
from typing import Union
from zoneinfo import ZoneInfo

from logprep.abc.exceptions import LogprepException

UTC = ZoneInfo("UTC")


class TimeParserException(LogprepException):
    """exception class for time parsing"""


class TimeParser:
    """encapsulation of time related methods"""

    @classmethod
    def from_string(cls, source: str, set_missing_utc: bool = True) -> datetime:
        """parses input string to datetime object

        Parameters
        ----------
        source : str
            input string
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

        Returns
        -------
        datetime
            datetime object
        """
        try:
            time_object = datetime.fromisoformat(source)  # pylint: disable=c-extension-no-member
            if set_missing_utc:
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
    def now(cls, timezone: tzinfo = None) -> datetime:
        """returns the current time

        Parameters
        ----------
        timezone : tzinfo
            the timezone to use for the timestamp

        Returns
        -------
        datetime
            current date and time as datetime
        """
        time_object = datetime.now(timezone)
        time_object = cls._set_utc_if_timezone_is_missing(time_object)
        return time_object

    @classmethod
    def from_format(cls, source: str, format_str: str, set_missing_utc: bool = True) -> datetime:
        """parse date from format

        Parameters
        ----------
        source : str
            the date string
        format_str : str
            the format string
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

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
            if set_missing_utc:
                time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @classmethod
    def _set_utc_if_timezone_is_missing(cls, time_object):
        if time_object.tzinfo is None:
            time_object = time_object.replace(tzinfo=UTC)
        return time_object

    @classmethod
    def parse_datetime(
        cls, timestamp: str, source_format: str, source_timezone: Union[str, tzinfo]
    ) -> datetime:
        """
        Parses a timestamp based on different formats, besides a format string 'ISO8601' and
        'UNIX' are allowed formats.

        Parameters
        ----------
        timestamp : str
            The timestamp string that should be parsed
        source_format : str
            The format which should be used to parse the timestamp string. Besides a format string
            'ISO8601' and 'UNIX' are allowed formats.
        source_timezone : str


        Returns
        -------
        datetime
            The parsed timestamp as datetime object.
        """
        if source_format == "UNIX":
            parsed_datetime = (
                int(timestamp)
                if len(timestamp) <= 10
                else int(timestamp) / 10 ** (len(timestamp) - 10)
            )
            parsed_datetime = cls.from_timestamp(parsed_datetime)
        elif source_format == "ISO8601":
            parsed_datetime = cls.from_string(timestamp, set_missing_utc=False)
        else:
            parsed_datetime = cls.from_format(timestamp, source_format, set_missing_utc=False)
            if parsed_datetime.year == 1900:
                parsed_datetime = parsed_datetime.replace(year=datetime.now().year)

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=source_timezone)

        return parsed_datetime
