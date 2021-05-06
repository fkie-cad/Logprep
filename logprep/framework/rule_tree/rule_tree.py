from typing import List
from json import load

from logging import Logger

from logprep.processor.base.rule import Rule

from logprep.framework.rule_tree.node import Node
from logprep.framework.rule_tree.rule_parser import RuleParser


class RuleTree:
    def __init__(self, root: Node = None, config_path: str = None):
        self.rule_counter = 0
        self._rule_mapping = {}
        self._config_path = config_path
        self._setup()

        if root:
            self._root = root
        else:
            self._root = Node('root')

    def _setup(self):
        self.priority_dict = {}
        self.tag_map = {}

        if self._config_path:
            with open(self._config_path, 'r') as file:
                config_data = load(file)

            self.priority_dict = config_data['priority_dict']
            self.tag_map = config_data['tag_map']

    def add_rule(self, rule: Rule, logger: Logger = None):
        try:
            parsed_rule_list = RuleParser.parse_rule(rule, self.priority_dict, self.tag_map)
        except Exception as ex:
            logger.warning('Error parsing rule "{}": {}: {}.\nIgnore and continue with next rule.'.format(
                rule.filter, type(ex).__name__, ex))
            return

        self.rule_counter += 1

        for parsed_rule in parsed_rule_list:
            end_node = self.add_parsed_rule(parsed_rule)
            end_node.matching_rule = rule

        self._rule_mapping[rule] = self.rule_counter - 1

    def add_parsed_rule(self, parsed_rule: list):
        current_node = self.root

        for expression in parsed_rule:
            if current_node.has_child_with_expression(expression):
                current_node = current_node.get_child_with_expression(expression)
                continue
            else:
                new_node = Node(expression)
                current_node.add_child(new_node)
                current_node = new_node

        return current_node

    def get_rule_id(self, rule: Rule) -> int:
        return self._rule_mapping[rule]

    def get_matching_rules(self, event: dict, current_node: Node = None, matches: List[Rule] = None) -> list:
        if not current_node:
            current_node = self._root
            matches = []

        for child in current_node.children:
            if child.does_match(event):
                current_node = child

                if current_node.matching_rule:
                    matches.append(child.matching_rule)

                self.get_matching_rules(event, current_node, matches)

        return matches

    def print(self, current_node: Node = None, depth: int = 1):
        if not current_node:
            current_node = self._root

        for child in current_node.children:
            print('\t' * (depth - 1) + str(current_node.expression), '\t', '-' * depth + '>', child.expression,
                  child.matching_rule)

            self.print(child, depth + 1)

    def get_size(self, current_node: Node = None) -> int:
        if not current_node:
            current_node = self._root

        size = 0
        size += len(current_node.children)

        for child in current_node.children:
            size += self.get_size(child)

        return size

    @property
    def root(self) -> Node:
        return self._root
