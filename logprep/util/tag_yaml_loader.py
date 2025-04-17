"""Load YAML files with include and anchor tags.
The tag `!include PATH_TO_YAML_FILE` loads a single yaml document from a file and inserts it at the
given spot.
The tag `!set_anchor ANCHOR_NAME` sets an anchor like using regular YAML anchors, but it is valid
for multiple documents within the same YAML stream (i.e. within a file).
It can be then loaded with `!load_anchor ANCHOR_NAME`.
"""

import os.path
from typing import Set

from ruamel.yaml import YAML, Loader, Node, BaseConstructor


def init_yaml_loader_tags(*loader_types: str) -> None:
    """Add custom tags !include, !set_anchor and !load_anchor to the specified loader types.

    Must be initialized before yaml files have been loaded to take effect.

    Parameters
    ----------
    *loader_types : str
        Types of loaders for which tags will be initialized (i.e. "safe" or "rt").
    """

    def include(_yaml: YAML):
        """Includes the contents of a yaml file specified by the !include tag.

        Parameters
        ----------
        _yaml : YAML
            Used to load the yaml file that will be included.

        Returns
        -------
        Yaml data where the !include tag has been replaced by the content of the include file.
        """

        def _include(_: Loader, node: Node):
            if not isinstance(node.value, (str, os.PathLike)):
                raise ValueError(f"'{node.value}' is not a file path")
            if not os.path.isfile(node.value):
                raise FileNotFoundError(node.value)
            with open(node.value, "r", encoding="utf-8") as yaml_file:
                data = _yaml.load(yaml_file)
                if data is None:
                    raise ValueError(f"'{node.value}' is empty")
                return data

        return _include

    def set_anchor(_yaml: YAML, _anchors: dict, _last_buffer: Set[str]):
        """Sets a global anchor if the '!set_anchor'tag is used, which is valid within a file.

        Setting it for a node with children stores the children inside the anchor.
        Setting it for a scalar node stores the value of that node inside the anchor.

        Parameters
        ----------
        _yaml : YAML
            Used to load the yaml file that will be included.
        _anchors : dict
            The dict where all anchors are stored.
        _last_buffer : Set[str]
            Used to check if a different file/stream has been loaded.

        Returns
        -------
        The loaded yaml data without any modifications.
        """
        tag = "!set_anchor"

        def _set_anchor(constructor: BaseConstructor, node: Node):
            clear_anchors_if_buffer_changed(constructor, _anchors, _last_buffer)

            anchor_name = get_anchor_name(tag, constructor, node)
            _anchors[anchor_name] = _extract_anchor_value(constructor, node)
            return _anchors[anchor_name]

        def _extract_anchor_value(constructor: BaseConstructor, node: Node):
            lines = constructor.loader.reader.buffer.splitlines()
            scalar_value = lines[node.start_mark.line]
            anchor_name = get_anchor_name(tag, constructor, node)
            _, _, scalar_value = scalar_value.partition(tag)
            _, _, scalar_value = scalar_value.partition(anchor_name)
            if scalar_value:
                anchor_value = scalar_value
            else:
                anchor_value = "\n".join(lines[node.start_mark.line + 1 : node.end_mark.line + 1])
            parsed_anchor_value = _yaml.load(anchor_value)
            if parsed_anchor_value is None:
                raise ValueError(f"'{lines[node.start_mark.line]}' is en empty scalar anchor")
            return _yaml.load(anchor_value)

        return _set_anchor

    def load_anchor(_anchors: dict, _last_buffer: Set[str]):
        """Loads a global anchor if the '!load_anchor'tag is used, which is valid within a file.

        Parameters
        ----------
        _anchors : dict
            The dict where all anchors are stored.
        _last_buffer : Set[str]
            Used to check if a different file/stream has been loaded.

        Returns
        -------
        Yaml data where the !load_anchor tag has been replaced by the content of the anchor.
        """

        def _load_anchor(constructor: BaseConstructor, node: Node):
            clear_anchors_if_buffer_changed(constructor, _anchors, _last_buffer)

            anchor_name = get_anchor_name("!load_anchor", constructor, node)
            try:
                return _anchors[anchor_name]
            except KeyError:
                raise ValueError(f"'{node.value}' is not a defined anchor within this yaml stream")

        return _load_anchor

    def clear_anchors_if_buffer_changed(
        constructor: BaseConstructor, _anchors: dict, _last_buffer: Set[str]
    ):
        if constructor.loader.reader.buffer not in _last_buffer:
            _last_buffer.clear()
            _anchors.clear()
            _last_buffer.add(constructor.loader.reader.buffer)

    def get_anchor_name(tag: str, constructor: BaseConstructor, node: Node) -> str:
        lines = constructor.loader.reader.buffer.splitlines()
        _, _, anchor_name = lines[node.start_mark.line][node.start_mark.column :].partition(tag)
        anchor_name = anchor_name.strip()
        anchor_name = anchor_name.split()[0]
        return anchor_name

    for loader_type in loader_types:
        yaml = YAML(pure=True, typ=loader_type)

        yaml.constructor.add_constructor("!include", include(yaml))

        last_buffer = set()
        anchors = {}
        yaml.constructor.add_constructor("!set_anchor", set_anchor(yaml, anchors, last_buffer))
        yaml.constructor.add_constructor("!load_anchor", load_anchor(anchors, last_buffer))
