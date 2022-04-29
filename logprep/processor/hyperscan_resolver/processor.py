"""This module contains functionality for resolving log event values using regex lists."""

import errno
from logging import Logger, DEBUG
from multiprocessing import current_process
from os import path, makedirs
from typing import List

# pylint: disable=no-name-in-module
from hyperscan import (
    Database,
    HS_FLAG_SINGLEMATCH,
    HS_FLAG_CASELESS,
    loadb,
    dumpb,
)

# pylint: enable=no-name-in-module

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule
from logprep.util.processor_stats import ProcessorStats


class HyperscanResolverError(BaseException):
    """Base class for HyperscanResolver related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"HyperscanResolver ({name}): {message}")


class DuplicationError(HyperscanResolverError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the Generic Resolver: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class HyperscanResolver(RuleBasedProcessor):
    """Resolve values in documents by referencing a mapping list."""

    def __init__(
        self,
        name: str,
        configuration: dict,
        logger: Logger,
    ):
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        tree_config = configuration.get("tree_config")
        super().__init__(name, tree_config, logger)
        self._hyperscan_databases = {}

        hyperscan_db_path = configuration.get("hyperscan_db_path")
        if hyperscan_db_path:
            self._hyperscan_database_path = hyperscan_db_path
        else:
            self._hyperscan_database_path = f"{path.dirname(path.abspath(__file__))}/hyperscan_dbs/"
        self.ps = ProcessorStats()

        self._event = None

        self._replacements_from_file = {}

        self.add_rules_from_directory(specific_rules_dirs, generic_rules_dirs)

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """Add rules from given directory."""
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = HyperscanResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = HyperscanResolverRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"({current_process().name})"
            )

        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=arguments-differ

    def _apply_rules(self, event, rule):
        """Apply the given rule to the current event"""
        conflicting_fields = []

        hyperscan_db, pattern_id_to_dest_val_map = self._get_hyperscan_database(rule)

        for resolve_source, resolve_target in rule.field_mapping.items():
            keys = resolve_target.split(".")
            src_val = self._get_dotted_field_value(event, resolve_source)

            if src_val:
                result = []

                def on_match(matching_pattern_id: int, _fr, _to, _flags, _context):
                    result.append(matching_pattern_id)

                hyperscan_db.scan(src_val, match_event_handler=on_match)

                if result:
                    dict_ = event
                    for idx, key in enumerate(keys):
                        if key not in dict_:
                            if idx == len(keys) - 1:
                                if rule.append_to_list:
                                    dict_[key] = dict_.get("key", [])
                                    dict_[key].append(
                                        pattern_id_to_dest_val_map[
                                            result[result.index(min(result))]
                                        ]
                                    )
                                else:
                                    dict_[key] = pattern_id_to_dest_val_map[
                                        result[result.index(min(result))]
                                    ]
                                break
                            dict_[key] = {}
                        if isinstance(dict_[key], dict):
                            dict_ = dict_[key]
                        else:
                            if rule.append_to_list and isinstance(dict_[key], list):
                                if (
                                    pattern_id_to_dest_val_map[result[result.index(min(result))]]
                                    not in dict_[key]
                                ):
                                    dict_[key].append(
                                        pattern_id_to_dest_val_map[
                                            result[result.index(min(result))]
                                        ]
                                    )
                            else:
                                conflicting_fields.append(keys[idx])

        if conflicting_fields:
            raise DuplicationError(self._name, conflicting_fields)

    def _get_hyperscan_database(self, rule):
        database_id = rule.file_name
        resolve_list = rule.resolve_list

        if database_id not in self._hyperscan_databases:
            try:
                database, value_mapping = self._load_database(database_id, resolve_list)
            except FileNotFoundError:
                database, value_mapping = self._create_database(resolve_list)

                if rule.store_db_persistent:
                    self._save_database(database, database_id)

            self._hyperscan_databases[database_id] = {}
            self._hyperscan_databases[database_id]["db"] = database
            self._hyperscan_databases[database_id]["value_mapping"] = value_mapping

        return (
            self._hyperscan_databases[database_id]["db"],
            self._hyperscan_databases[database_id]["value_mapping"],
        )

    def _load_database(self, database_id, resolve_list):
        value_mapping = {}

        with open(self._hyperscan_database_path + "/" + database_id + ".db", "rb") as db_file:
            data = db_file.read()

        for idx, pattern in enumerate(resolve_list.keys()):
            value_mapping[idx] = resolve_list[pattern]

        return loadb(data), value_mapping

    def _save_database(self, database, database_id):
        _create_hyperscan_dbs_dir(self._hyperscan_database_path)
        serialized_db = dumpb(database)

        with open(self._hyperscan_database_path + "/" + database_id + ".db", "wb") as db_file:
            db_file.write(serialized_db)

    def _create_database(self, resolve_list):
        database = Database()
        value_mapping = {}
        db_patterns = []

        for idx, pattern in enumerate(resolve_list.keys()):
            db_patterns += [(pattern.encode("utf-8"), idx, HS_FLAG_SINGLEMATCH | HS_FLAG_CASELESS)]
            value_mapping[idx] = resolve_list[pattern]

        if not db_patterns:
            raise HyperscanResolverError(self._name, "No patter to compile for hyperscan database!")

        expressions, ids, flags = zip(*db_patterns)
        database.compile(expressions=expressions, ids=ids, elements=len(db_patterns), flags=flags)

        return database, value_mapping


def _create_hyperscan_dbs_dir(path_):
    try:
        makedirs(path_)
    except OSError as error:
        if error.errno != errno.EEXIST:
            raise
