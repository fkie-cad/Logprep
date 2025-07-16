# Logprep Copilot Instructions

## Architecture Overview

Logprep is a log processing pipeline system that follows a **connector-processor-connector** pattern:
- **Connectors**: Handle input/output (Kafka, Opensearch, S3, HTTP, files)
- **Processors**: Transform events in sequential pipelines (dissector, geoip_enricher, dropper, etc.)
- **Pipelines**: Multi-process execution of processor chains

Key directories:
- `logprep/connector/`: Legacy connector implementations
- `logprep/ng/`: Next-generation components (active development)
- `logprep/processor/`: 30+ processors for log transformation
- `logprep/abc/`: Abstract base classes defining interfaces

## Development Patterns

### Component Structure
All components follow this pattern:
```python
class Component:
    @define(kw_only=True)
    class Config(BaseClass.Config):
        # Configuration parameters with validators
    
    @define(kw_only=True) 
    class Metrics(BaseClass.Metrics):
        # Prometheus metrics with CounterMetric/HistogramMetric
```

### Processor Implementation
Each processor has `processor.py` and `rule.py`:
- Inherit from `logprep.abc.processor.Processor`
- Implement `_apply_rules()` method
- Rules define if/how to process events
- Use `logprep.util.helper` for field manipulation

### Testing
- All tests in `tests/unit/` mirror source structure
- Base test classes: `BaseComponentTestCase`, `BaseConnectorTestCase`
- Use `Factory.create()` for component instantiation in tests
- Coverage requirement: 100%

## Current Development Context

**Active work**: Adding next-generation (`ng/`) connectors
- Branch: `dev-make-connectors-store-logevents`
- New `ng/` connectors use `Event` objects instead of raw dicts
- Registry pattern for component discovery in `logprep/registry.py`

## Build & Development

### Setup
```bash
pip install -e .[dev]  # Install with dev dependencies
pre-commit install     # Enable hooks
```

### Testing
```bash
pytest ./tests --cov=logprep --cov-report=xml -vvv
```

### Hybrid Python/Rust
- Rust extensions in `rust/` directory with PyO3 bindings
- Build with `setuptools-rust` in `pyproject.toml`

## Configuration System

YAML-based configuration with three levels:
1. **Pipeline config**: Defines processor chain and connectors
2. **Processor rules**: YAML files defining transformation logic
3. **Component configs**: Type-specific parameters from Processor.Config

Example processor config:
```yaml
- dissector:
    type: dissector
    rules: ["rules/01_dissector/"]
```

## Key Utilities

- `logprep.util.helper`: Field manipulation (`get_dotted_field_value`, `add_fields_to`)
- `logprep.util.time.TimeParser`: Time related utilities, encapsulates external libraries
- `logprep.framework.pipeline`: Pipeline setup and execution
- `logprep.factory.Factory`: Component instantiation

## Conventions

- Use `attrs` for data classes with `@define(kw_only=True)`
- Metrics naming: `logprep_[component]_[metric_name]`
- Exception hierarchy: Component-specific exceptions inherit from base module
- File naming: `processor.py`, `rule.py`, `output.py`, `input.py`
- Branch naming: `dev-[feature]` or `fix-[issue]`

## Integration Points

- **Registry system**: Auto-discovery in `logprep/registry.py`
- **Metrics**: Prometheus integration via `logprep.metrics`
- **Configuration**: HTTP or filesystem-based YAML configs
- **Multiprocessing**: Pipeline manager creates pipelines and spawns worker processes
- **Event flow**: Input → Pipeline (Processors) → Output with error handling
