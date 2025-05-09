"""
Logprep supports the custom YAML tags `!include`, `!set_anchor` and `!load_anchor`.
Those can be used inside any YAML file that is loaded by Logprep.

Include tags
^^^^^^^^^^^^

The tag `!include PATH_TO_YAML_FILE` loads a single YAML document from a local file path and inserts
it in its place.

Included files can't contain an `!include` tag.

Example:

..  code-block:: yaml
    :linenos:
    :caption: Include tag

    filter: to_resolve
    generic_resolver:
        field_mapping:
            to_resolve: resolved
        resolve_list: !include /path/to/resolve_list.yml

Anchor tags
^^^^^^^^^^^

Anchor tags work similar to regular YAML anchors, but are valid for all documents inside a file or
stream.
Tags are set with `!set_anchor(:[0-9])?` and loaded with `!load_anchor(:[0-9])?`.
Ten anchors can be active inside a single file or stream.
`!set_anchor` and `!load_anchor` are shorthands for `!set_anchor:0` and `!load_anchor:0`.

`!include` and `!set_anchor` can't be nested inside `!set_anchor`.

Examples:

..  code-block:: yaml
    :linenos:
    :caption: Anchor tag without shorthand

    filter: to_resolve
    generic_resolver:
        field_mapping:
            to_resolve: resolved
        resolve_list: !set_anchor:1
            one: foo
            two: bar
    ---
    filter: to_resolve_2
    generic_resolver:
        field_mapping:
            to_resolve_2: resolved
        resolve_list: !load_anchor:1

..  code-block:: yaml
    :linenos:
    :caption: Anchor tag with shorthand

    filter: to_resolve
    generic_resolver:
        field_mapping:
            to_resolve: resolved
        resolve_list: !set_anchor
            one: foo
            two: bar
    ---
    filter: to_resolve_2
    generic_resolver:
        field_mapping:
            to_resolve_2: resolved
        resolve_list: !load_anchor
"""

import os.path
from typing import Set

from ruamel.yaml import YAML, Node, BaseConstructor


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

        def _include(_: BaseConstructor, node: Node):
            if not isinstance(node.value, (str, os.PathLike)):
                raise ValueError(f"'{node.value}' is not a file path")
            if not os.path.isfile(node.value):
                raise FileNotFoundError(node.value)
            with open(node.value, "r", encoding="utf-8") as yaml_file:
                try:
                    data = _yaml.load(yaml_file)
                except AttributeError as error:
                    raise ValueError(f"'{node.tag} {node.value}' could not be loaded") from error
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

        def _set_anchor(constructor: BaseConstructor, node: Node):
            clear_anchors_if_buffer_changed(constructor, _anchors, _last_buffer)

            anchor_name = get_anchor_name(node)
            _anchors[anchor_name] = _extract_anchor_value(constructor, node)
            return _anchors[anchor_name]

        def _extract_anchor_value(constructor: BaseConstructor, node: Node):
            lines = constructor.loader.reader.buffer.splitlines()
            anchor_value_lines = lines[node.start_mark.line : node.end_mark.line + 1]
            anchor_value_lines[0] = anchor_value_lines[0][node.start_mark.column + len(node.tag) :]
            anchor_value_lines[-1] = anchor_value_lines[-1][: node.end_mark.column]
            anchor_value = "\n".join(anchor_value_lines)
            try:
                data = _yaml.load(anchor_value)
            except AttributeError as error:
                _, _, value = "\\n".join(lines).partition(node.tag)
                raise ValueError(f"'{node.tag}{value}' could not be loaded") from error
            if data is None:
                raise ValueError(f"'{lines[node.start_mark.line]}' is en empty anchor")
            return data

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

            anchor_name = get_anchor_name(node)
            try:
                return _anchors[anchor_name]
            except KeyError as error:
                raise ValueError(
                    f"'{node.value}' is not a defined anchor within this yaml stream"
                ) from error

        return _load_anchor

    def clear_anchors_if_buffer_changed(
        constructor: BaseConstructor, _anchors: dict, _last_buffer: Set[str]
    ):
        if constructor.loader.reader.buffer not in _last_buffer:
            _last_buffer.clear()
            _anchors.clear()
            _last_buffer.add(constructor.loader.reader.buffer)

    def get_anchor_name(node: Node) -> str:
        _, _, anchor_name = node.tag.partition(":")
        if anchor_name == "":
            anchor_name = "0"
        anchor_name = anchor_name.strip()
        return anchor_name

    for loader_type in loader_types:
        yaml = YAML(pure=True, typ=loader_type)

        yaml.constructor.add_constructor("!include", include(yaml))

        last_buffer: Set[str] = set()
        anchors: dict = {}
        yaml.constructor.add_constructor("!set_anchor", set_anchor(yaml, anchors, last_buffer))
        yaml.constructor.add_constructor("!load_anchor", load_anchor(anchors, last_buffer))

        for num in range(10):
            yaml.constructor.add_constructor(
                f"!set_anchor:{num}", set_anchor(yaml, anchors, last_buffer)
            )
            yaml.constructor.add_constructor(
                f"!load_anchor:{num}", load_anchor(anchors, last_buffer)
            )
