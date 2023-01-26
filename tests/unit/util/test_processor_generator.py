# pylint: disable=missing-docstring

from pathlib import Path
from logprep.abc.processor import Processor
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.processor_generator import ProcessorGenerator


class TestProcessorGenerator:

    processor_path = Path("logprep/processor/test_processor")
    processor_test_path = Path("tests/unit/processor/test_processor")

    def teardown_method(self):
        for path in (self.processor_path, self.processor_test_path):
            if path.exists():
                for file in path.iterdir():
                    file.unlink(missing_ok=True)
                path.rmdir()

    def test_create_generator_returns_generator(self):
        config = {"name": "test_processor"}
        generator = ProcessorGenerator(**config)
        assert generator
        assert generator.name == "test_processor"

    def test_property_class_name_returns_name(self):
        config = {"name": "test_processor"}
        generator = ProcessorGenerator(**config)
        assert generator.class_name == "TestProcessor"

    def test_call_with_class_name_sets_name(self):
        config = {"name": "TestProcessor"}
        generator = ProcessorGenerator(**config)
        assert generator.class_name == "TestProcessor"
        assert generator.name == "test_processor"

    def test_sets_default_base_class(self):
        config = {"name": "TestProcessor"}
        generator = ProcessorGenerator(**config)
        assert generator.base_class == Processor

    def test_sets_base_class_by_snake_case_name(self):
        config = {"name": "TestProcessor", "base_class": "field_manager"}
        generator = ProcessorGenerator(**config)
        assert generator.base_class == FieldManager

    def test_sets_base_class_by_camel_case_name(self):
        config = {"name": "TestProcessor", "base_class": "FieldManager"}
        generator = ProcessorGenerator(**config)
        assert generator.base_class == FieldManager

    def test_processor_path_returns_path(self):
        config = {"name": "TestProcessor", "base_class": "FieldManager"}
        generator = ProcessorGenerator(**config)
        assert generator.processor_path == self.processor_path
        assert generator.processor_unit_test_path == self.processor_test_path

    def test_generate_creates_files(self):
        config = {"name": "TestProcessor", "base_class": "FieldManager"}
        generator = ProcessorGenerator(**config)
        generator.generate()
        assert self.processor_path.exists()
        assert (self.processor_path / "processor.py").exists()
        assert (self.processor_path / "rule.py").exists()
        assert (self.processor_path / "__init__.py").exists()
        assert self.processor_test_path.exists()
        assert self.processor_test_path / "test_test_processor.py"
        assert self.processor_test_path / "test_test_processor_rule.py"
        assert self.processor_test_path / "__init__.py"

    def test_generator_renders_template(self):
        config = {"name": "TestProcessor", "base_class": "FieldManager"}
        generator = ProcessorGenerator(**config)
        assert "class TestProcessor(FieldManager):" in generator.processor_code
