"""
===================
Processor Generator
===================

generates boilerplate code to implement a new processor for logprep
"""

import sys
from typing import Type
from pathlib import Path
from attrs import field, validators, define
from jinja2 import Template

from logprep.abc.processor import Processor
from logprep.util.helper import snake_to_camel, camel_to_snake
from logprep.registry import Registry

PROCESSOR_BASE_PATH = "logprep/processor"
PROCESSOR_UNIT_TEST_BASE_PATH = "tests/unit/processor"
PROCESSOR_TEMPLATE_PATH = "logprep/util/template_processor.py.j2"
RULE_TEMPLATE_PATH = "logprep/util/template_rule.py.j2"
PROCESSOR_TEST_TEMPLATE_PATH = "logprep/util/template_processor_test.py.j2"


def get_class(processor_name: str) -> type:
    """returns the type by str"""
    if isinstance(processor_name, type):
        return processor_name
    return Registry.get_class(camel_to_snake(processor_name))


@define(kw_only=True)
class ProcessorGenerator:
    """Processor generator"""

    name: str = field(validator=validators.instance_of(str), converter=camel_to_snake)

    base_class: Type = field(
        validator=validators.instance_of(Type), default=Processor, converter=get_class
    )

    @property
    def class_name(self) -> str:
        """returns the class_name"""
        return snake_to_camel(self.name)

    @property
    def processor_path(self) -> Path:
        """returns the processor path"""
        return Path(PROCESSOR_BASE_PATH) / self.name

    @property
    def processor_unit_test_path(self) -> Path:
        """returns the processor path"""
        return Path(PROCESSOR_UNIT_TEST_BASE_PATH) / self.name

    @property
    def processor_template(self) -> Template:
        """returns the processor template"""
        return Template(Path(PROCESSOR_TEMPLATE_PATH).read_text(encoding="utf8"))

    @property
    def processor_code(self) -> str:
        """returns the rendered template"""
        return self.processor_template.render({"processor": self})

    @property
    def rule_template(self) -> Template:
        """returns the rule template"""
        return Template(Path(RULE_TEMPLATE_PATH).read_text(encoding="utf8"))

    @property
    def rule_code(self) -> str:
        """returns the rendered template"""
        return self.rule_template.render({"processor": self})

    @property
    def processor_test_template(self) -> Template:
        """returns the processor_test template"""
        return Template(Path(PROCESSOR_TEST_TEMPLATE_PATH).read_text(encoding="utf8"))

    @property
    def processor_test_code(self) -> str:
        """returns the rendered template"""
        return self.processor_test_template.render({"processor": self})

    def generate(self):
        """creates processor boilerplate"""
        if not self.processor_path.exists():
            self.processor_path.mkdir()
            (self.processor_path / "processor.py").write_text(self.processor_code)
            (self.processor_path / "rule.py").write_text(self.rule_code)
            (self.processor_path / "__init__.py").touch()
        if not self.processor_unit_test_path.exists():
            self.processor_unit_test_path.mkdir()
            (self.processor_unit_test_path / f"test_{self.name}.py").touch()
            (self.processor_unit_test_path / f"test_{self.name}_rule.py").touch()
            (self.processor_unit_test_path / "__init__.py").touch()
