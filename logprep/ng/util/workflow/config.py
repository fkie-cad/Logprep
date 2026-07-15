"""
Configuration for the workers.
"""

from typing import Literal, Self, TypeAlias, get_args

from attrs import define, field, validators

from logprep.util.converters import convert_from_dict

ConfigurableWorkerName: TypeAlias = Literal[
    "processing_worker",
    "extra_output_worker",
    "output_worker",
    "error_worker",
    "acknowledge_worker",
]

WorkerName: TypeAlias = Literal["input_worker"] | ConfigurableWorkerName

_CONFIGURABLE_WORKER_NAMES: frozenset[str] = frozenset(get_args(ConfigurableWorkerName))


@define(kw_only=True)
class WorkerConfig:
    """
    Configuration for a single worker.
    """

    queue_size: int = field(
        validator=(validators.instance_of(int), validators.ge(1)),
        default=5000,
    )
    """
    Maximum amount of items in the input queue for this component.
    Reaching this limit puts backpressure on upstream producers.
    Needs to be higher than `batch_size`.
    """

    @staticmethod
    def _validate_batch_size_lt_queue_size(config: "WorkerConfig", _, batch_size: int):
        if batch_size > config.queue_size:
            raise ValueError("batch_size needs to exceed queue_size for worker configuration")

    batch_size: int = field(
        validator=(
            validators.instance_of(int),
            validators.ge(1),
            _validate_batch_size_lt_queue_size,
        ),
        default=5000,
    )
    """
    Desired amount of items to be processed as one batch.
    Batches may be processed in parallel, but not necessarily.
    """

    batch_interval_s: float = field(
        validator=(validators.instance_of(float), validators.gt(0)),
        converter=float,
        default=5.0,
    )
    """
    Maximum amount of time between flushing batches.
    """


@define(kw_only=True)
class WorkflowConfig:
    """
    Configuration for a whole workflow.
    """

    @staticmethod
    def _validate_all_workers_present(_, __, value: dict[WorkerName, WorkerConfig]) -> None:
        if value.keys() != _CONFIGURABLE_WORKER_NAMES:
            missing = _CONFIGURABLE_WORKER_NAMES - value.keys()
            extraneous = value.keys() - _CONFIGURABLE_WORKER_NAMES
            raise ValueError(f"Misconfigured workers: missing={missing}, extraneous={extraneous}")

    workers: dict[WorkerName, WorkerConfig] = field(
        validator=validators.deep_mapping(
            key_validator=validators.in_(_CONFIGURABLE_WORKER_NAMES),
            value_validator=validators.instance_of(WorkerConfig),
            mapping_validator=_validate_all_workers_present,
        ),
        converter=lambda d: {
            name: convert_from_dict(WorkerConfig, d.get(name, {}))
            for name in _CONFIGURABLE_WORKER_NAMES
        },
        factory=dict,
    )
    """
    A `WorkerConfig` for each worker participating in the workflow
    """

    @classmethod
    def from_dict_or_default(cls, config: dict | None = None) -> Self:
        """Convenience method for creating a `WorkflowConfig` with defaults from a dict"""
        return cls(**(config if config is not None else {}))
