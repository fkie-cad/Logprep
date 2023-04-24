"""logprep time helpers module"""
from datetime import datetime
from typing import Union

import arrow
import ciso8601


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
            return ciso8601.parse_datetime(source)  # pylint: disable=c-extension-no-member
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
        return datetime.fromtimestamp(timestamp)

    @staticmethod
    def now() -> datetime:
        """returns the current time

        Returns
        -------
        datetime
            current date and time as datetime
        """
        return datetime.now()

    @staticmethod
    def from_format(source: str, format_str: str) -> datetime:
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
            return arrow.get(source, format_str).datetime
        except arrow.parser.ParserError as error:
            raise TimeParserException(str(error)) from error
