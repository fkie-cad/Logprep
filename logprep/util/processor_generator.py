"""
===================
Processor Generator
===================

generates boilerplate code to implement a new processor for logprep
"""

from pathlib import Path
from attrs import field, validators, define

from logprep.abc.processor import Processor
from logprep.util.helper import snake_to_camel, camel_to_snake
from logprep.registry import Registry

PROCESSOR_BASE_PATH = "logprep/processor"
PROCESSOR_UNIT_TEST_BASE_PATH = "tests/unit/processor"


def get_class(processor_name: str | type) -> type:
    """returns the type by str"""
    if isinstance(processor_name, type):
        return processor_name
    return Registry.get_class(camel_to_snake(processor_name))


@define(kw_only=True)
class ProcessorGenerator:
    """Processor generator"""

    name: str = field(validator=validators.instance_of(str), converter=camel_to_snake)

    base_class: type = field(
        validator=validators.instance_of(type), default=Processor, converter=get_class
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

    def generate(self):
        """creates processor boilerplate"""
        if not self.processor_path.exists():
            self.processor_path.mkdir()
            (self.processor_path / "processor.py").touch()
            (self.processor_path / "rule.py").touch()
            (self.processor_path / "__init__.py").touch()
        if not self.processor_unit_test_path.exists():
            self.processor_unit_test_path.mkdir()
            (self.processor_unit_test_path / f"test_{self.name}.py").touch()
            (self.processor_unit_test_path / f"test_{self.name}_rule.py").touch()
            (self.processor_unit_test_path / "__init__.py").touch()
