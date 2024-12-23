"""
HyperscanResolver
=================

The `hyperscan_resolver` is a processor that can resolve fields by using a map of resolve patterns
and resolve values. The map can be defined within rules or within a file. It uses python hyperscan
to speedup the pattern matching.
It works similarly to the generic resolver, but utilized hyperscan to process resolve lists.

For further information see: `GenericResolver`_.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - hyperscanresolvername:
        type: hyperscan_resolver
        rules:
            - tests/testdata/rules/rules
        hyperscan_db_path: tmp/path/scan.db

.. autoclass:: logprep.processor.hyperscan_resolver.processor.HyperscanResolver.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.hyperscan_resolver.rule
"""

import errno
from os import makedirs, path
from typing import Any, Dict, Tuple

from attr import define, field

from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
    SkipImportError,
)
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import add_fields_to, get_dotted_field_value
from logprep.util.validators import directory_validator

# pylint: disable=no-name-in-module
try:
    from hyperscan import HS_FLAG_CASELESS, HS_FLAG_SINGLEMATCH, Database, dumpb, loadb
except ModuleNotFoundError as error:  # pragma: no cover
    raise SkipImportError("hyperscan_resolver") from error

# pylint: enable=no-name-in-module

# pylint: disable=ungrouped-imports
from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule

# pylint: enable=ungrouped-imports


class HyperscanResolver(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
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

    def __init__(self, name: str, configuration: FieldManager.Config):
        super().__init__(name=name, configuration=configuration)
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

        source_values = []
        for resolve_source, resolve_target in rule.field_mapping.items():
            src_val = get_dotted_field_value(event, resolve_source)
            source_values.append(src_val)
            matches = self._match_with_hyperscan(hyperscan_db, src_val)
            if matches:
                dest_val = pattern_id_to_dest_val_map[matches[matches.index(min(matches))]]
                if dest_val:
                    current_content = get_dotted_field_value(event, resolve_target)
                    if isinstance(current_content, list) and dest_val in current_content:
                        continue
                    if rule.merge_with_target and current_content is None:
                        dest_val = [dest_val]
                    try:
                        add_fields_to(
                            event,
                            fields={resolve_target: dest_val},
                            rule=rule,
                            merge_with_target=rule.merge_with_target,
                            overwrite_target=rule.overwrite_target,
                        )
                    except FieldExistsWarning as error:
                        conflicting_fields.extend(error.skipped_fields)
        self._handle_missing_fields(event, rule, rule.field_mapping.keys(), source_values)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

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
                database, value_mapping = self._create_database(resolve_list, rule)

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

    def _create_database(self, resolve_list: dict, rule):
        database = Database()
        value_mapping = {}
        db_patterns = []

        for idx, pattern in enumerate(resolve_list.keys()):
            db_patterns += [(pattern.encode("utf-8"), idx, HS_FLAG_SINGLEMATCH | HS_FLAG_CASELESS)]
            value_mapping[idx] = resolve_list[pattern]

        if not db_patterns:
            raise ProcessingCriticalError(
                f"{self.name} No patter to compile for hyperscan database!", rule
            )

        expressions, ids, flags = zip(*db_patterns)
        database.compile(expressions=expressions, ids=ids, elements=len(db_patterns), flags=flags)

        return database, value_mapping


def _create_hyperscan_dbs_dir(path_: str):
    try:
        makedirs(path_)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
