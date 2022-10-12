"""
HyperscanResolver
-----------------

The `hyperscan_resolver` is a processor that can resolve fields by using a map of resolve patterns
and resolve values. The map can be defined within rules or within a file. It uses pythion hyperscan
to speedup the pattern matching.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - hyperscanresolvername:
        type: hyperscan_resolver
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        hyperscan_db_path: tmp/path/scan.db
"""

import errno
from logging import Logger
from os import path, makedirs
from typing import List, Tuple, Any, Dict
from attr import define, field

from logprep.abc import Processor
from logprep.processor.base.exceptions import SkipImportError
from logprep.util.validators import directory_validator
from logprep.util.helper import get_dotted_field_value

# pylint: disable=no-name-in-module
try:
    from hyperscan import (
        Database,
        HS_FLAG_SINGLEMATCH,
        HS_FLAG_CASELESS,
        loadb,
        dumpb,
    )
except ModuleNotFoundError as error:  # pragma: no cover
    raise SkipImportError("hyperscan_resolver") from error

# pylint: enable=no-name-in-module

from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule


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


class HyperscanResolver(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """HyperscanResolver config"""

        hyperscan_db_path: str = field(validator=directory_validator)
        """Path to a directory where the compiled
        `Hyperscan <https://python-hyperscan.readthedocs.io/en/latest/>`_
        databases will be stored persistently.
        Persistent storage is set to false per default.
        If the specified directory does not exist, it will be created.
        The database will be stored in the directory of the `hyperscan_resolver` if no path has
        been specified within the pipeline config.
        To update and recompile a persistently stored databases simply delete the whole directory.
        The databases will be compiled again during the next run."""

    __slots__ = ["_hyperscan_database_path", "_hyperscan_databases", "_replacements_from_file"]

    _replacements_from_file: dict

    _hyperscan_database_path: str

    _hyperscan_databases: dict

    rule_class = HyperscanResolverRule

    def __init__(
        self,
        name: str,
        configuration: Processor.Config,
        logger: Logger,
    ):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self._hyperscan_databases = {}

        hyperscan_db_path = configuration.hyperscan_db_path
        if hyperscan_db_path:
            self._hyperscan_database_path = hyperscan_db_path
        else:
            self._hyperscan_database_path = f"{path.dirname(path.abspath(__file__))}/hyperscan_dbs/"

        self._replacements_from_file = {}

    def _apply_rules(self, event: dict, rule: HyperscanResolverRule):
        """Apply the given rule to the current event"""
        conflicting_fields = []
        hyperscan_db, pattern_id_to_dest_val_map = self._get_hyperscan_database(rule)

        for resolve_source, resolve_target in rule.field_mapping.items():
            src_val = get_dotted_field_value(event, resolve_source)
            result = self._match_with_hyperscan(hyperscan_db, src_val)

            if result:
                has_conflict = False
                resolved_value = pattern_id_to_dest_val_map[result[result.index(min(result))]]
                split_dotted_keys = resolve_target.split(".")
                dict_ = event

                for idx, dotted_key_part in enumerate(split_dotted_keys):
                    last_idx = len(split_dotted_keys) - 1
                    key_is_new = dotted_key_part not in dict_
                    if key_is_new and idx < last_idx:
                        dict_[dotted_key_part] = {}

                    if key_is_new and idx == last_idx:
                        self._add_new_key_with_value(dict_, dotted_key_part, resolved_value, rule)
                    elif isinstance(dict_[dotted_key_part], dict):
                        dict_ = dict_[dotted_key_part]
                    else:
                        has_conflict = self._try_adding_value_to_existing_field(
                            dict_, dotted_key_part, resolved_value, rule
                        )

                    if has_conflict:
                        conflicting_fields.append(split_dotted_keys[idx])
        if conflicting_fields:
            raise DuplicationError(self.name, conflicting_fields)

    @staticmethod
    def _try_adding_value_to_existing_field(
        dict_: dict, dotted_key_part: str, resolved_value: str, rule: HyperscanResolverRule
    ) -> bool:
        current_value = dict_[dotted_key_part]
        if rule.append_to_list and isinstance(current_value, list):
            if resolved_value not in current_value:
                current_value.append(resolved_value)
            return False
        return True

    @staticmethod
    def _add_new_key_with_value(
        dict_: dict, dotted_key_part: str, resolved_value: str, rule: HyperscanResolverRule
    ):
        if rule.append_to_list:
            dict_[dotted_key_part] = dict_.get("key", [])
            dict_[dotted_key_part].append(resolved_value)
        else:
            dict_[dotted_key_part] = resolved_value

    @staticmethod
    def _match_with_hyperscan(hyperscan_db: Database, src_val: str) -> list:
        if not src_val:
            return []

        def on_match(matching_pattern_id: int, _fr, _to, _flags, _context):
            result.append(matching_pattern_id)

        result = []

        hyperscan_db.scan(src_val.encode("utf-8"), match_event_handler=on_match)
        return result

    def _get_hyperscan_database(self, rule: HyperscanResolverRule):
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

    def _load_database(self, database_id: int, resolve_list: dict) -> Tuple[Any, Dict[int, Any]]:
        value_mapping = {}

        with open(f"{self._hyperscan_database_path}/{database_id}.db", "rb") as db_file:
            data = db_file.read()

        for idx, pattern in enumerate(resolve_list.keys()):
            value_mapping[idx] = resolve_list[pattern]

        return loadb(data), value_mapping

    def _save_database(self, database: Database, database_id: int):
        _create_hyperscan_dbs_dir(self._hyperscan_database_path)
        serialized_db = dumpb(database)

        with open(f"{self._hyperscan_database_path}/{database_id}.db", "wb") as db_file:
            db_file.write(serialized_db)

    def _create_database(self, resolve_list: dict):
        database = Database()
        value_mapping = {}
        db_patterns = []

        for idx, pattern in enumerate(resolve_list.keys()):
            db_patterns += [(pattern.encode("utf-8"), idx, HS_FLAG_SINGLEMATCH | HS_FLAG_CASELESS)]
            value_mapping[idx] = resolve_list[pattern]

        if not db_patterns:
            raise HyperscanResolverError(self.name, "No patter to compile for hyperscan database!")

        expressions, ids, flags = zip(*db_patterns)
        database.compile(expressions=expressions, ids=ids, elements=len(db_patterns), flags=flags)

        return database, value_mapping


def _create_hyperscan_dbs_dir(path_: str):
    try:
        makedirs(path_)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
