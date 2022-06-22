"""This module is used to connect to a MySQL database and to retrieve data from a SQL table."""

import time
from logging import Logger

import pymysql
import pymysql.cursors


class MySQLConnector:
    """Used to connect to a MySQL database and to retrieve data from a table if it has changed."""

    connection: pymysql.connections.Connection

    target_column: str

    _add_target_column: bool

    table_name: str

    _timer: int

    _last_check: int

    _last_table_checksum: str

    _logger: Logger

    _cursor: pymysql.cursors.Cursor

    def __init__(self, sql_config: dict, logger: Logger):
        """Initialize the MySQLConnector.

        Parameters
        ----------
        sql_config : dict
           SQL configuration dictionary.
        logger : logging.Logger
           Logger to use.

        Returns
        -------
        bool
            True if the SQL table has changed, False otherwise.

        """
        self._logger = logger

        self.connection = pymysql.connect(
            user=sql_config["user"],
            password=sql_config["password"],
            host=sql_config["host"],
            database=sql_config["database"],
            port=sql_config.get("port", 3306),
            cursorclass=pymysql.cursors.DictCursor,
        )
        self._cursor = self.connection.cursor
        self.target_column = sql_config["target_column"]
        self._add_target_column = sql_config.get("add_target_column", False)

        self.table_name = sql_config["table"]

        self._timer = sql_config.get("timer", 60 * 3)
        self._last_check = 0
        self._last_table_checksum = None

    def has_changed(self) -> bool:
        """Check if a configured SQL table has changed.

        The checksum of the table is used to check if a table has changed. The check is only
        performed if a specified time has passed since the last check.

        Returns
        -------
        bool
            True if the SQL table has changed, False otherwise.

        """
        if time.time() - self._last_check >= self._timer:
            self._last_check = time.time()
            checksum = self._get_checksum()
            if self._last_table_checksum is None:
                self._last_table_checksum = checksum
                return True
            if self._last_table_checksum == checksum:
                return False
            return True
        return False

    def _get_checksum(self) -> int:
        """Get the checksum a configured SQL table.

        The checksum is used to check if a table has changed.

        Returns
        -------
        int
            The checksum of a SQL table.

            This value changes if the table or it's contents change.

        """

        with self.connection:
            with self._cursor() as cursor:
                # you cant use the arguments cause it puts it in single quotes which leads to SQL Error
                sql = f"CHECKSUM TABLE {self.table_name}"  # nosemgrep
                cursor.execute(sql)
                _, checksum = cursor.fetchone()
                return checksum

    def get_data(self) -> dict:
        """Get addition data from a configured SQL table.

        Returns
        -------
        dict
            A dict containing a mapping to rows that can be added by the generic adder.

            The keys of the dict are the values in the SQL table that are being compared to a value
            in the event. The values in the dict are lists containing keys and values that can be
            added by the generic adder if there is a match.

        """
        self._last_table_checksum = self._get_checksum()

        try:
            with self.connection:
                with self._cursor() as cursor:
                    # you cant use the arguments cause it puts it in single quotes which leads to SQL Error
                    cursor.execute(f"SELECT * FROM {self.table_name}")  # nosemgrep

                    # TODO the returned dict has to be translated to meet the tests but I have no clue how it was done
                    result = cursor.fetchall()
                    return result

        except self.connection.Error as error:
            self._logger.warning(f"Error retrieving entry from database: {error}")
            return {}
