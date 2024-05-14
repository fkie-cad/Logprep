# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
from logprep.generator.kafka.configuration import validate


def get_config():
    config_dict = {
        "count": 1,
        "source_count": 1,
        "kafka": {
            "bootstrap_servers": ["foo.bar.baz"],
            "producer": {"topic": "foo"},
            "consumer": {"topic": "bar", "group_id": "baz"},
        },
    }
    config = validate(config_dict)
    return config
