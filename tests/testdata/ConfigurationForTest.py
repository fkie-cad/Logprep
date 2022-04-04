from tempfile import NamedTemporaryFile

from yaml import dump, safe_load

from tests.testdata.metadata import path_to_config, path_to_schema, path_to_rules


class ConfigurationForTest:
    def __init__(self, change={}, remove=[], inject_changes=[]):
        self._temp_file = None
        with open(path_to_config, "r") as file:
            self.config = safe_load(file)

        self.config["labeling_scheme"] = path_to_schema
        self.config["rules"] = [path_to_rules]

        self.config.update(change)

        for aware_change in inject_changes:
            self._inject_change(aware_change)

        for keys in remove:
            self._remove(keys)

    def __enter__(self):
        self._temp_file = NamedTemporaryFile(mode="w")
        dump(self.config, self._temp_file)
        self._temp_file.flush()

        return self._temp_file.name

    def _remove(self, dictionary, keys):
        if len(keys) == 1:
            del dictionary[keys[0]]
        else:
            self._remove(dictionary[keys[0]], keys[1:])

    def _inject_change(self, change):
        self._change_recursively(self.config, change)

    def _change_recursively(self, parent, changes):
        for sub_key in changes:
            if isinstance(changes[sub_key], dict):
                self._change_recursively(parent[sub_key], changes[sub_key])
            else:
                parent[sub_key] = changes[sub_key]

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._temp_file is not None:
            self._temp_file.close()
