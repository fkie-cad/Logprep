"""This module is used to connect to a MySQL database and to retrieve data from a SQL table."""

import time
from logging import Logger
from typing import Optional

import mysql
import mysql.connector as db


class MySQLConnector:
    """Used to connect to a MySQL database and to retrieve data from a table if it has changed."""

    connection: Optional[mysql.connector.MySQLConnection]

    target_column: str
    """The name of the column whose values are being matched against a value from an event"""

    _add_target_column: bool
    """Determines if the target column itself will be added to the event"""

    table_name: str
    """The table name to use when connecting to the MySQL database"""

    _db_check_interval: float
    """Time that has to pass for the database to be checked"""

    _last_check: float
    """Last time the database has been checked"""

    _last_table_checksum: Optional[int]
    """Checksum of the database table that was obtained on the last update check"""

    _logger: Logger

    _cursor: mysql.connector.connection.CursorBase

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

        self.connection = None
        self.cursor = None

        self._sql_config = sql_config

        self.target_column = sql_config["target_column"]
        self._add_target_column = sql_config.get("add_target_column", False)

        self.table_name = sql_config["table"]

        self._db_check_interval = sql_config.get("timer", 60 * 3)
        self._last_check = 0
        self._last_table_checksum = None

    def connect(self):
        """Get connection to SQL database and cursor for database table"""
        self.connection = db.connect(
            user=self._sql_config["user"],
            password=self._sql_config["password"],
            host=self._sql_config["host"],
            database=self._sql_config["database"],
            port=self._sql_config.get("port", 3306),
        )
        self.cursor = self.connection.cursor()

    def disconnect(self):
        """Close connection to SQL database"""
        self.connection.close()

    def time_to_check_for_change(self) -> bool:
        """Check if enough time has passed to check for a SQL table change.

        Update the timer if it is time to check for a change.

        Returns
        -------
        bool
            True if a check should be performed, False otherwise.

        """
        check_change = time.time() - self._last_check >= self._db_check_interval
        if check_change:
            self._last_check = time.time()
        return check_change

    def has_changed(self) -> bool:
        """Check if a configured SQL table has changed.

        The checksum of the table is used to check if a table has changed. The check is only
        performed if a specified time has passed since the last check.

        Returns
        -------
        bool
            True if the SQL table has changed, False otherwise.

        """
        checksum = self._get_checksum()
        if self._last_table_checksum == checksum:
            return False
        self._last_table_checksum = checksum
        return True

    def _get_checksum(self) -> int:
        """Get the checksum a configured SQL table.

        The checksum is used to check if a table has changed.

        Returns
        -------
        int
            The checksum of a SQL table.

            This value changes if the table or it's contents change.

        """
        self.cursor.execute(f"CHECKSUM TABLE {self.table_name}")  # nosemgrep
        checksum = next(self.cursor)[-1]
        self.connection.commit()
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

        table = {}
        target_col = 0

        try:
            self.cursor.execute(f"desc {self.table_name}")  # nosemgrep
            col_names = []
            for idx, column_desc in enumerate(self.cursor):
                col_names.append(column_desc[0])
                if column_desc[0] == self.target_column:
                    target_col = idx

            self.cursor.execute(f"SELECT * FROM {self.table_name}")  # nosemgrep

            for row_vals in self.cursor:
                if self._add_target_column:
                    column_dict = tuple(
                        (
                            [col_names[idx], col]
                            for idx, col in enumerate(row_vals)
                            if col_names[idx].upper() != "ID"
                        )
                    )
                else:
                    column_dict = tuple(
                        (
                            [col_names[idx], col]
                            for idx, col in enumerate(row_vals)
                            if idx != target_col and col_names[idx].upper() != "ID"
                        )
                    )
                table[row_vals[target_col].upper()] = column_dict

            return table
        except db.Error as error:
            self._logger.warning(f"Error retrieving entry from database: {error}")
            return {}
