"""This module contains functionality for adding fields using regex lists."""
from logging import Logger, DEBUG
from multiprocessing import current_process
from typing import List

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.generic_adder.mysql_connector import MySQLConnector
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.util.processor_stats import ProcessorStats


class GenericAdderError(BaseException):
    """Base class for GenericAdder related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericAdder ({name}): {message}")


class DuplicationError(GenericAdderError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and were not overwritten by the GenericAdder: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GenericAdder(RuleBasedProcessor):
    """Add arbitrary fields and values to a processed events.

    Fields and values can be added directly from the rule definition or from a file specified within
    a rule. Furthermore, a SQL table can be used to to add multiple keys and values if a specified
    field's value within the SQL table matches a specified field's value withing the rule
    definition.

    The generic adder can not overwrite existing values.

    """

    db_table = None

    def __init__(self, name: str, configuration: dict, logger: Logger):
        """Initialize a generic adder instance.

        Performs a basic processor initialization. Furthermore, a SQL database and a SQL table are
        being initialized if a SQL configuration exists.

        Parameters
        ----------
        name : str
           Name for the generic adder.
        configuration : dict
           Configuration for SQL adding and rule loading.
        logger : logging.Logger
           Logger to use.

        """
        tree_config = configuration.get("tree_config")
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        sql_config = configuration.get("sql_config")
        super().__init__(name, tree_config, logger)

        self._db_connector = MySQLConnector(sql_config, logger) if sql_config else None

        if GenericAdder.db_table is None:
            GenericAdder.db_table = self._db_connector.get_data() if self._db_connector else None
        self._db_table = GenericAdder.db_table

        self.ps = ProcessorStats()
        self.add_rules_from_directory(
            generic_rules_dirs=generic_rules_dirs,
            specific_rules_dirs=specific_rules_dirs,
        )

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = GenericAdderRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = GenericAdderRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"generic rules ({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

    def _apply_rules(self, event: dict, rule: GenericAdderRule):
        """Apply a matching generic adder rule to the event.

         Add fields and values to the event according to the rules it matches for.
        Additions can come from the rule definition, from a file or from a SQL table.

        The SQL table is initially loaded from the database and then reloaded if it changes.

        At first it checks if a SQL table exists and if it will be used. If it does, it adds all
        values from a matching row in the table to the event. To determine if a row matches, a
        pattern is used on a defined value of the event to extract a subvalue that is then matched
        against a value in a defined column of the SQL table. A dotted path prefix can be applied to
        add the new fields into a shared nested location.

        If no table exists, fields defined withing the rule itself or in a rule file are being added
        to the event.

        Parameters
        ----------
        event : dict
           Name of the event to add keys and values to.
        rule : GenericAdderRule
           A matching generic adder rule.

        Raises
        ------
        DuplicationError
            Raises if an addition would overwrite an existing field or value.

        """

        if self._db_connector and self._db_connector.check_change():
            self._db_table = self._db_connector.get_data()

        conflicting_fields = []

        # Either add items from a sql db table or from the rule definition and/or a file
        if rule.db_target and self._db_table:
            # Create items to add from a db table
            items_to_add = []
            if rule.db_pattern:
                # Get the sub part of the value from the event using a regex pattern
                value_to_check_in_db = self._get_dotted_field_value(event, rule.db_target)
                match_with_value_in_db = rule.db_pattern.match(value_to_check_in_db)
                if match_with_value_in_db:
                    # Get values to add from db table using the sub part
                    value_to_map = match_with_value_in_db.group(1).upper()
                    to_add_from_db = self._db_table.get(value_to_map, [])
                    for item in to_add_from_db:
                        if rule.db_destination_prefix:
                            if not item[0].startswith(rule.db_destination_prefix):
                                item[0] = f"{rule.db_destination_prefix}.{item[0]}"
                        items_to_add.append(item)
        else:
            # Use items from rule definition and/or file
            items_to_add = rule.add.items()

        # Add the items to the event
        for dotted_field, value in items_to_add:
            keys = dotted_field.split(".")
            dict_ = event
            for idx, key in enumerate(keys):
                if key not in dict_:
                    if idx == len(keys) - 1:
                        dict_[key] = value
                        break
                    dict_[key] = {}

                if isinstance(dict_[key], dict):
                    dict_ = dict_[key]
                else:
                    conflicting_fields.append(keys[idx])

        if conflicting_fields:
            raise DuplicationError(self._name, conflicting_fields)
