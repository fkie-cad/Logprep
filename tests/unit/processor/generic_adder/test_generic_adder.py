# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=unused-argument
import json
import os
import tempfile
import time
from copy import deepcopy
from unittest import mock

import pytest

from logprep.processor.generic_adder.processor import DuplicationError
from logprep.processor.generic_adder.rule import InvalidGenericAdderDefinition
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from tests.unit.processor.base import BaseProcessorTestCase

RULES_DIR_MISSING = "tests/testdata/unit/generic_adder/rules_missing"
RULES_DIR_INVALID = "tests/testdata/unit/generic_adder/rules_invalid"
RULES_DIR_FIRST_EXISTING = "tests/testdata/unit/generic_adder/rules_first_existing"


BASE_TABLE_RESULTS = [
    [0, "TEST_0", "foo", "bar"],
    [1, "TEST_1", "uuu", "vvv"],
    [2, "TEST_2", "123", "456"],
]


def mock_simulate_table_change():
    DBMock.Cursor.checksum += 1
    DBMock.Cursor.table_result[0] = [0, "TEST_0", "fi", "fo"]


class DBMock(mock.MagicMock):
    class Cursor:
        table_result = deepcopy(BASE_TABLE_RESULTS)
        checksum = 0

        def __init__(self):
            self._data = []

        def execute(self, statement):
            if statement == "CHECKSUM TABLE test_table":
                self._data = [self.checksum]
            elif statement == "desc test_table":
                self._data = [["id"], ["a"], ["b"], ["c"]]
            elif statement == "SELECT * FROM test_table":
                self._data = self.table_result
            else:
                self._data = []

        def mock_clear_all(self):
            self.checksum = 0
            self._data = []
            self.table_result = []

        def __next__(self):
            return self._data

        def __iter__(self):
            return iter(self._data)

    def cursor(self):
        return self.Cursor()

    def commit(self):
        pass


class DBMockNeverEmpty(DBMock):
    class Cursor(DBMock.Cursor):
        def execute(self, statement):
            if statement.startswith("CHECKSUM TABLE "):
                self._data = [self.checksum]
            elif statement.startswith("desc "):
                self._data = [["id"], ["a"], ["b"], ["c"]]
            elif statement.startswith("SELECT * FROM "):
                self._data = self.table_result
            else:
                self._data = []


class TestGenericAdder(BaseProcessorTestCase):

    CONFIG = {
        "type": "generic_adder",
        "generic_rules": ["tests/testdata/unit/generic_adder/rules/generic"],
        "specific_rules": ["tests/testdata/unit/generic_adder/rules/specific"],
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")

    def test_db_table_is_none(self):
        assert self.object._db_table is None

    def test_add_generic_fields(self):
        assert self.object.metrics.number_of_processed_events == 0
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file(self):
        assert self.object.metrics.number_of_processed_events == 0
        expected = {
            "add_list_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_list_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_one_element(self):
        assert self.object.metrics.number_of_processed_events == 0
        expected = {
            "add_lists_one_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_lists_one_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_two_elements(self):
        assert self.object.metrics.number_of_processed_events == 0
        expected = {
            "add_lists_two_generic_test": "Test",
            "event_id": 123,
            "added_from_other_file": "some field from another file",
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_lists_two_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing(self):
        config = deepcopy(self.CONFIG)
        config["generic_rules"] = [RULES_DIR_FIRST_EXISTING]
        configuration = {"test processor": config}
        generic_adder = Factory.create(configuration, self.logger)

        assert generic_adder.metrics.number_of_processed_events == 0
        expected = {
            "add_first_existing_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_first_existing_generic_test": "Test", "event_id": 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing_with_missing(self):
        config = deepcopy(self.CONFIG)
        config["specific_rules"] = [RULES_DIR_FIRST_EXISTING]
        configuration = {"test_instance_name": config}
        generic_adder = Factory.create(configuration, self.logger)

        assert generic_adder.metrics.number_of_processed_events == 0
        expected = {
            "add_first_existing_with_missing_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {
            "add_first_existing_with_missing_generic_test": "Test",
            "event_id": 123,
        }

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidGenericAdderDefinition, match=r"files do not exist"):
            config = deepcopy(self.CONFIG)
            config["specific_rules"] = [RULES_DIR_MISSING]
            configuration = {"test_instance_name": config}
            Factory.create(configuration, self.logger)

    def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(
            InvalidGenericAdderDefinition,
            match=r"must be a dictionary with string values",
        ):

            config = deepcopy(self.CONFIG)
            config["generic_rules"] = [RULES_DIR_INVALID]
            configuration = {"test processor": config}
            Factory.create(configuration, self.logger)

    def test_add_generic_fields_to_co_existing_field(self):
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}, "i_exist": "already"},
        }
        document = {
            "add_generic_test": "Test",
            "event_id": 123,
            "dotted": {"i_exist": "already"},
        }

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_to_existing_value(self):
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some_non_dict",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some_non_dict",
        }

        with pytest.raises(DuplicationError):
            self.object.process(document)

        assert document == expected


class BaseTestGenericAdderSQLTestCase(BaseProcessorTestCase):
    def setup_method(self):
        super().setup_method()
        DBMock.Cursor.table_result = deepcopy(BASE_TABLE_RESULTS)
        if os.path.isfile(self.object._db_file_path):
            os.remove(self.object._db_file_path)
        self.object._initialize_sql(self.CONFIG["sql_config"])

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")


class TestGenericAdderProcessorSQLWithoutAddedTarget(BaseTestGenericAdderSQLTestCase):
    mocks = {"mysql.connector.connect": {"return_value": DBMock()}}

    CONFIG = {
        "type": "generic_adder",
        "generic_rules": ["tests/testdata/unit/generic_adder/rules/generic"],
        "specific_rules": ["tests/testdata/unit/generic_adder/rules/specific"],
        "sql_config": {
            "user": "test_user",
            "password": "foo_bar_baz",
            "host": "127.0.0.1",
            "database": "test_db",
            "table": "test_table",
            "target_column": "a",
            "timer": 0.1,
        },
    }

    def test_load_from_file(self):
        expected_db = {
            "TEST_0": (["b", "foo"], ["c", "bar"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }

        assert self.object._db_table == expected_db

        _, temp_path = tempfile.mkstemp()
        self.object._db_file_path = temp_path

        db_file_content = {"FOO": "BAR"}
        with open(temp_path, "w", encoding="utf8") as db_table:
            json.dump(db_file_content, db_table)
        self.object._load_from_file()

        assert self.object._db_table == db_file_content

    def test_check_if_file_not_stale_after_initialization_of_the_generic_adder(self):
        assert not self.object._check_if_file_not_exists_or_stale(time.time())

    def test_check_if_file_stale_after_enough_time_has_passed(self):
        time.sleep(0.2)  # nosemgrep
        assert self.object._check_if_file_not_exists_or_stale(time.time())

    def test_check_if_file_not_stale_after_enough_time_has_passed_but_file_has_been_changed(self):
        time.sleep(0.2)  # nosemgrep
        now = time.time()
        os.utime(self.object._db_file_path, (now, now))  # Simulates change of file
        assert not self.object._check_if_file_not_exists_or_stale(now)

    def test_check_if_file_stale_after_removing_it_when_it_was_not_stale(self):
        assert not self.object._check_if_file_not_exists_or_stale(time.time())
        os.remove(self.object._db_file_path)
        assert self.object._check_if_file_not_exists_or_stale(time.time())

    def test_sql_database_enriches_via_table(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "foo", "c": "bar"}},
        }
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object.process(document)

        assert document == expected

    def test_sql_database_enriches_via_table_ignore_case(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "test_0.test.123",
            "db": {"test": {"b": "foo", "c": "bar"}},
        }
        document = {"add_from_sql_db_table": "Test", "source": "test_0.test.123"}

        self.object.process(document)

        assert document == expected

    def test_sql_database_does_not_enrich_via_table_if_value_does_not_exist(self):
        expected = {"add_from_sql_db_table": "Test", "source": "TEST_I_DO_NOT_EXIST.test.123"}
        document = {"add_from_sql_db_table": "Test", "source": "TEST_I_DO_NOT_EXIST.test.123"}

        self.object.process(document)

        assert document == expected

    def test_sql_database_does_not_enrich_via_table_if_pattern_does_not_match(self):
        expected = {"add_from_sql_db_table": "Test", "source": "TEST_0%FOO"}
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0%FOO"}

        self.object.process(document)

        assert document == expected

    def test_sql_database_reloads_table_on_change_after_wait(self):
        expected_1 = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "foo", "c": "bar"}},
        }
        expected_2 = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "fi", "c": "fo"}},
        }
        document_1 = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}
        document_2 = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object.process(document_1)
        time.sleep(0.2)  # nosemgrep
        mock_simulate_table_change()
        self.object.process(document_2)

        assert document_1 == expected_1
        assert document_2 == expected_2

    def test_sql_database_with_empty_table_load_after_change(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "fi", "c": "fo"}},
        }
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object._db_table = {}
        self.object._initialize_sql(self.CONFIG["sql_config"])
        mock_simulate_table_change()
        time.sleep(0.2)  # nosemgrep
        self.object.process(document)

        assert document == expected

    def test_sql_database_does_not_reload_table_on_change_if_no_wait(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "foo", "c": "bar"}},
        }
        document_1 = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}
        document_2 = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object.process(document_1)
        mock_simulate_table_change()
        self.object.process(document_2)

        assert document_1 == expected
        assert document_2 == expected

    def test_sql_database_raises_exception_on_duplicate(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"b": "foo", "c": "bar"}},
        }
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object.process(document)
        with pytest.raises(DuplicationError):
            self.object.process(document)

        assert document == expected

    def test_time_to_check_for_change_not_read_for_change(self):
        self.object._file_check_interval = 9999999
        assert self.object._db_connector.time_to_check_for_change() is False

    def test_time_to_check_for_change_read_for_change(self):
        time.sleep(self.object._file_check_interval)  # nosemgrep
        assert self.object._db_connector.time_to_check_for_change() is True

    def test_update_from_db_and_write_to_file_change_and_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        last_file_change = os.path.getmtime(self.object._db_file_path)
        mock_simulate_table_change()
        time.sleep(self.object._file_check_interval)  # nosemgrep
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "fi"], ["c", "fo"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.getmtime(self.object._db_file_path) > last_file_change

    def test_update_from_db_and_write_to_file_no_change_and_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        last_file_change = os.path.getmtime(self.object._db_file_path)
        time.sleep(self.object._file_check_interval)  # nosemgrep
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "foo"], ["c", "bar"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.getmtime(self.object._db_file_path) == last_file_change

    def test_update_from_db_and_write_to_file_change_and_not_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        last_file_change = os.path.getmtime(self.object._db_file_path)
        self.object._file_check_interval = 9999999
        mock_simulate_table_change()
        time.sleep(0.01)  # nosemgrep
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "fi"], ["c", "fo"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.getmtime(self.object._db_file_path) > last_file_change

    def test_update_from_db_and_write_to_file_no_change_and_not_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        last_file_change = os.path.getmtime(self.object._db_file_path)
        self.object._file_check_interval = 9999999
        time.sleep(0.01)  # nosemgrep
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "foo"], ["c", "bar"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.getmtime(self.object._db_file_path) == last_file_change

    def test_update_from_db_and_write_to_file_no_existing_file_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        os.remove(self.object._db_file_path)
        time.sleep(self.object._file_check_interval)  # nosemgrep
        self.object._db_connector._last_table_checksum = None
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "foo"], ["c", "bar"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.isfile(self.object._db_file_path)

    def test_update_from_db_and_write_to_file_no_existing_file_not_stale(self):
        assert os.path.isfile(self.object._db_file_path)
        os.remove(self.object._db_file_path)
        self.object._file_check_interval = 9999999
        self.object._db_connector._last_table_checksum = None
        self.object._update_from_db_and_write_to_file()
        assert self.object._db_table == {
            "TEST_0": (["b", "foo"], ["c", "bar"]),
            "TEST_1": (["b", "uuu"], ["c", "vvv"]),
            "TEST_2": (["b", "123"], ["c", "456"]),
        }
        assert os.path.isfile(self.object._db_file_path)


class TestGenericAdderProcessorSQLWithoutAddedTargetAndTableNeverEmpty(
    BaseTestGenericAdderSQLTestCase
):
    mocks = {"mysql.connector.connect": {"return_value": DBMockNeverEmpty()}}

    CONFIG = TestGenericAdderProcessorSQLWithoutAddedTarget.CONFIG

    def test_sql_database_no_enrichment_with_empty_table(self):
        expected = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object._db_connector.cursor.mock_clear_all()
        self.object._db_table = {}
        self.object.process(document)

        assert document == expected

    @pytest.mark.parametrize(
        "test_case, table, raised_error",
        [
            (
                "valid table name only alpha",
                "table",
                None,
            ),
            (
                "valid table name only numeric",
                "0",
                None,
            ),
            (
                "valid table name only alphanumeric",
                "0a1b",
                None,
            ),
            (
                "valid table name alphanumeric and underscore",
                "0a_1b",
                None,
            ),
            (
                "not alphanumeric",
                "table!",
                (
                    InvalidConfigurationError,
                    "Table in 'sql_config' may only contain "
                    + "alphanumeric characters and underscores!",
                ),
            ),
            (
                "whitespace",
                "tab le",
                (
                    InvalidConfigurationError,
                    "Table in 'sql_config' contains whitespaces!",
                ),
            ),
            (
                "not alphanumeric and whitespace",
                "tab le!",
                (
                    InvalidConfigurationError,
                    "Table in 'sql_config' contains whitespaces!",
                ),
            ),
        ],
    )
    def test_sql_table_must_contain_only_alphanumeric_or_underscore(
        self, test_case, table, raised_error
    ):
        config = deepcopy(self.CONFIG)
        config["sql_config"]["table"] = table

        if raised_error:
            with pytest.raises(raised_error[0], match=raised_error[1]):
                Factory.create({"Test Instance Name": config}, self.logger)
        else:
            Factory.create({"Test Instance Name": config}, self.logger)


class TestGenericAdderProcessorSQLWithAddedTarget(BaseTestGenericAdderSQLTestCase):
    mocks = {"mysql.connector.connect": {"return_value": DBMock()}}

    CONFIG = {
        "type": "generic_adder",
        "generic_rules": ["tests/testdata/unit/generic_adder/rules/generic"],
        "specific_rules": ["tests/testdata/unit/generic_adder/rules/specific"],
        "sql_config": {
            "user": "test_user",
            "password": "foo_bar_baz",
            "host": "127.0.0.1",
            "database": "test_db",
            "table": "test_table",
            "target_column": "a",
            "add_target_column": True,
            "timer": 0.1,
        },
    }

    def test_db_table_is_not_none(self):
        assert self.object._db_table is not None

    def test_sql_database_adds_target_field(self):
        expected = {
            "add_from_sql_db_table": "Test",
            "source": "TEST_0.test.123",
            "db": {"test": {"a": "TEST_0", "b": "foo", "c": "bar"}},
        }
        document = {"add_from_sql_db_table": "Test", "source": "TEST_0.test.123"}

        self.object.process(document)

        assert document == expected
