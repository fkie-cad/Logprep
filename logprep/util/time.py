"""Logprep time helpers module"""

from datetime import UTC, datetime, tzinfo

from logprep.abc.exceptions import LogprepException


class TimeParserException(LogprepException):
    """Exception class for time parsing"""


class TimeParser:
    """Encapsulation of time related methods"""

    @classmethod
    def from_string(cls, source: str, set_missing_utc: bool = True) -> datetime:
        """Parses input string to datetime object.

        Parameters
        ----------
        source : str
            Input string in ISO8601 format
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

        Returns
        -------
        datetime
            Datetime object

        Raises
        ------
        TimeParserException
            Raises if source can't be parsed as datetime object from ISO8601 format
        """
        try:
            time_object = datetime.fromisoformat(source)  # pylint: disable=c-extension-no-member
            if set_missing_utc:
                time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @classmethod
    def from_unix_timestamp(cls, timestamp: int | float) -> datetime:
        """Get datetime from unix timestamp.

        Parameters
        ----------
        timestamp : int | float
            Unix timestamp

        Returns
        -------
        datetime
            Datetime object

        Raises
        ------
        TimeParserException
            Raises if timestamp can't be parsed as datetime object from unix timestamp format
        """
        try:
            time_object = datetime.fromtimestamp(timestamp, tz=UTC)
            time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except TypeError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def now(timezone: tzinfo | None = UTC) -> datetime:
        """Returns the current time.

        Parameters
        ----------
        timezone : tzinfo | None
            The timezone to use for the timestamp

        Returns
        -------
        datetime
            Current date and time as datetime
        """
        timezone = timezone if timezone else UTC
        time_object = datetime.now(timezone)
        return time_object

    @classmethod
    def from_format(cls, source: str, format_str: str, set_missing_utc: bool = True) -> datetime:
        """Parse date from format.

        Parameters
        ----------
        source : str
            The date string
        format_str : str
            The format string
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

        Returns
        -------
        datetime
            The datetime object

        Raises
        ------
        TimeParserException
            Raised if something could not be parsed
        """
        try:
            time_object = datetime.strptime(source, format_str)
            if set_missing_utc:
                time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def _set_utc_if_timezone_is_missing(time_object: datetime) -> datetime:
        if time_object.tzinfo is None:
            time_object = time_object.replace(tzinfo=UTC)
        return time_object

    @staticmethod
    def _normalize_unix_timestamp(timestamp: str) -> int | float:
        """Normalize the input timestamp string to unix timestamp in seconds.

        Unix timestamps are assumed to be in seconds if the timestamp has 10 digits
        or fewer before the decimal point, since seconds with more than 10 digits
        would be far into the future. Timestamps with more than 10 digits before
        the decimal point are scaled down so that 10 digits remain before the
        decimal point.

        Timestamp strings with a decimal point are parsed as float so fractional
        seconds are preserved.

        Parameters
        ----------
        timestamp : str
            The date string in unix timestamp format

        Returns
        -------
        int | float
            Unix timestamp parsed as number in seconds

        Raises
        ------
        TimeParserException
            Raised if input timestamp string could not be parsed as a number
        """
        try:
            timestamp = timestamp.strip()
            integer_part = TimeParser._get_unix_timestamp_integer_part(timestamp)

            if "." in timestamp:
                return TimeParser._normalize_fractional_unix_timestamp(timestamp, integer_part)

            return TimeParser._normalize_integer_unix_timestamp(timestamp, integer_part)
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def _get_unix_timestamp_integer_part(timestamp: str) -> str:
        """Return the integer part of a UNIX timestamp."""
        return timestamp.split(".", maxsplit=1)[0]

    @staticmethod
    def _normalize_fractional_unix_timestamp(timestamp: str, integer_part: str) -> float:
        """Normalize a fractional UNIX timestamp to seconds.

        Fractional UNIX timestamps are parsed as float to preserve sub-second
        precision. The digit-count heuristic is applied to the integer part only.
        """
        parsed_timestamp = float(timestamp)
        return (
            parsed_timestamp
            if len(integer_part) <= 10
            else parsed_timestamp / 10 ** (len(integer_part) - 10)
        )

    @staticmethod
    def _normalize_integer_unix_timestamp(timestamp: str, integer_part: str) -> int | float:
        """Normalize an integer-only UNIX timestamp to seconds.

        Existing behavior is preserved: timestamps with 10 digits or fewer are
        interpreted as seconds. Longer values are scaled down so that 10 digits
        remain before the decimal point.
        """
        return (
            int(timestamp)
            if len(integer_part) <= 10
            else int(timestamp) / 10 ** (len(integer_part) - 10)
        )

    @classmethod
    def parse_datetime(
        cls, timestamp: str, source_format: str, source_timezone: tzinfo
    ) -> datetime:
        """Parse a timestamp based on different formats.

        A format string, 'ISO8601' and 'UNIX' are allowed formats.

        Parameters
        ----------
        timestamp : str
            The timestamp string that should be parsed
        source_format : str
            The format which should be used to parse the timestamp string. Besides a format string
            'ISO8601' and 'UNIX' are allowed formats.
        source_timezone : tzinfo


        Returns
        -------
        datetime
            The parsed timestamp as datetime object.
        """
        if source_format == "UNIX":
            normalized_unix_timestamp = cls._normalize_unix_timestamp(timestamp)
            parsed_datetime = cls.from_unix_timestamp(normalized_unix_timestamp)
        elif source_format == "ISO8601":
            parsed_datetime = cls.from_string(timestamp, set_missing_utc=False)
        else:
            parsed_datetime = cls.from_format(timestamp, source_format, set_missing_utc=False)
            if parsed_datetime.year == 1900:
                parsed_datetime = parsed_datetime.replace(year=datetime.now().year)

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=source_timezone)

        return parsed_datetime
