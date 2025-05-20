"""
Logprep supports the custom YAML tags :code:`!include`, :code:`!set_anchor` and
:code:`!load_anchor`.
Those can be used inside any YAML file that is loaded by Logprep.

Include tags
^^^^^^^^^^^^

The tag :code:`!include PATH_TO_YAML_FILE` loads a single YAML document from a local file path and
inserts it in its place.

Included files can't contain an :code:`!include` tag.

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

Anchor tags work similar to regular YAML anchors, but are valid across different documents.
Tags are set with :code:`!set_anchor(:[0-9])?` and loaded with :code:`!load_anchor(:[0-9])?`.
Ten anchors can be active at the same time. If more then ten are set then the first will be removed
until there are ten.
`!set_anchor` and :code:`!load_anchor` are shorthands for :code:`!set_anchor:0` and
:code:`!load_anchor:0`.

`!set_anchor` can't be nested inside another :code:`!set_anchor`.

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
from typing import Callable, Any

from ruamel.yaml import (
    YAML,
    Node,
    BaseConstructor,
    ScalarNode,
    SequenceNode,
    MappingNode,
    RoundTripConstructor,
)


def _include(_yaml: YAML) -> Callable[[BaseConstructor, Node], Any]:
    """Includes the contents of a yaml file specified by the !include tag.

    Parameters
    ----------
    _yaml : YAML
        Used to load the yaml file that will be included.

    Returns
    -------
    Yaml data where the !include tag has been replaced by the content of the include file.
    """

    def _include_inner(_: BaseConstructor, node: Node) -> Any:
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

    return _include_inner


def _set_anchor(_yaml: YAML, _anchors: dict[str, Any]) -> Callable[[BaseConstructor, Node], Any]:
    """Sets a global anchor if the '!set_anchor'tag is used, which is valid within a file.

    Setting it for a node with children stores the children inside the anchor.
    Setting it for a scalar node stores the value of that node inside the anchor.

    Parameters
    ----------
    _yaml : YAML
        Used to load the yaml file that will be included.
    _anchors : dict[str, Any]
        The dict where all anchors are stored.

    Returns
    -------
    The loaded yaml data without any modifications.
    """

    def _set_anchor_inner(constructor: BaseConstructor, node: Node) -> Any:
        anchor_name = _get_anchor_name(node)
        _anchors[anchor_name] = _extract_anchor_value(constructor, node)
        return _anchors[anchor_name]

    def _parse_node(constructor: BaseConstructor, node: Node) -> Any:
        if node.value == "":
            raise ValueError(f"{node.tag} is an empty anchor")

        if isinstance(node, ScalarNode):
            return constructor.construct_scalar(node)

        if isinstance(constructor, RoundTripConstructor):
            if isinstance(node, SequenceNode):
                return list(constructor.construct_yaml_seq(node))[0]
            if isinstance(node, MappingNode):
                return list(constructor.construct_yaml_map(node))[0]

        if isinstance(node, SequenceNode):
            return constructor.construct_sequence(node)
        if isinstance(node, MappingNode):
            return constructor.construct_mapping(node)
        return {}

    def _extract_anchor_value(constructor: BaseConstructor, node: Node) -> Any:
        try:
            data = _parse_node(constructor, node)
        except AttributeError as error:
            raise ValueError(f"'{node.tag} {node.value}' could not be loaded") from error
        if data is None:
            raise ValueError(f"{node.tag} is en empty anchor")
        return data

    return _set_anchor_inner


def _load_anchor(_anchors: dict[str, Any]) -> Callable[[BaseConstructor, Node], Any]:
    """Loads a global anchor if the '!load_anchor'tag is used, which is valid within a file.

    Parameters
    ----------
    _anchors : dict[str, Any]
        The dict where all anchors are stored.

    Returns
    -------
    Yaml data where the !load_anchor tag has been replaced by the content of the anchor.
    """

    def _load_anchor_inner(_: BaseConstructor, node: Node) -> Any:
        anchor_name = _get_anchor_name(node)
        try:
            return _anchors[anchor_name]
        except KeyError as error:
            raise ValueError(
                f"Global anchor '{anchor_name}' is not defined within this YAML stream"
            ) from error

    return _load_anchor_inner


def _get_anchor_name(node: Node) -> str:
    anchor_name: str
    _, _, anchor_name = node.tag.partition(":")
    if anchor_name == "":
        anchor_name = "0"
    anchor_name = anchor_name.strip()
    return anchor_name


def init_yaml_loader_tags(*loader_types: str) -> None:
    """Add custom tags !include, !set_anchor and !load_anchor to the specified loader types.

    Must be initialized before yaml files have been loaded to take effect.

    Parameters
    ----------
    *loader_types : str
        Types of loaders for which tags will be initialized (i.e. "safe" or "rt").
    """

    anchors: dict[str, Any] = {}

    for loader_type in loader_types:
        yaml = YAML(pure=True, typ=loader_type)
        yaml.constructor.add_constructor("!include", _include(yaml))

        yaml.constructor.add_constructor("!set_anchor", _set_anchor(yaml, anchors))
        yaml.constructor.add_constructor("!load_anchor", _load_anchor(anchors))

        for num in range(10):
            yaml.constructor.add_constructor(f"!set_anchor:{num}", _set_anchor(yaml, anchors))
            yaml.constructor.add_constructor(f"!load_anchor:{num}", _load_anchor(anchors))
