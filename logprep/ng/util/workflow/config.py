"""
Configuration for the workers.
"""

from typing import Literal, Self, TypeAlias, get_args

from attrs import define, field, validators

from logprep.util.converters import convert_from_dict

WorkerName: TypeAlias = Literal[
    "processing_worker",
    "extra_output_worker",
    "output_worker",
    "error_worker",
    "acknowledge_worker",
]

WORKER_NAMES: frozenset[str] = frozenset(get_args(WorkerName))


@define(kw_only=True)
class WorkerConfig:
    """
    Configuration for a single worker.
    """

    batch_size: int = field(
        validator=(validators.instance_of(int), validators.ge(1)),
        default=5000,
    )
    queue_size: int = field(
        validator=(validators.instance_of(int), validators.ge(1)),
        default=5000,
    )
    flush_interval_s: float = field(
        validator=(validators.instance_of(float), validators.gt(0)),
        converter=float,
        default=5.0,
    )


def _validate_all_workers_present(_, __, value: dict[WorkerName, WorkerConfig]) -> None:
    if value.keys() != WORKER_NAMES:
        missing = WORKER_NAMES - value.keys()
        extraneous = value.keys() - WORKER_NAMES
        raise ValueError(f"Misconfigured workers: missing={missing}, extraneous={extraneous}")


@define(kw_only=True)
class WorkflowConfig:
    """
    Configuration for a whole workflow.
    """

    workers: dict[WorkerName, WorkerConfig] = field(
        validator=validators.deep_mapping(
            key_validator=validators.in_(WORKER_NAMES),
            value_validator=validators.instance_of(WorkerConfig),
            mapping_validator=_validate_all_workers_present,
        ),
        converter=lambda d: {
            name: convert_from_dict(WorkerConfig, d.get(name, {})) for name in WORKER_NAMES
        },
        factory=dict,
    )

    @classmethod
    def from_dict_or_default(cls, config: dict | None = None) -> Self:
        """Convenience method for creating a `WorkflowConfig` with defaults from a dict"""
        return cls(**(config if config is not None else {}))
