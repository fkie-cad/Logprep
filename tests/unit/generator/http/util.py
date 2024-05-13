# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import json
import os

import yaml


def create_test_event_files(
    root_path,
    sample_event,
    number_of_events,
    file_name="events.jsonl",
    class_name="test_class",
    config=None,
):
    event_class_dir = root_path / class_name
    os.makedirs(event_class_dir, exist_ok=True)
    events_file_path = event_class_dir / file_name
    events = []
    for i in range(number_of_events):
        sample_event.update({"id": i})
        events.append(json.dumps(sample_event))
    events_file_path.write_text("\n".join(events))
    if config is None:
        event_class_config = {"target_path": f"/target-{class_name}"}
    else:
        event_class_config = config
    config_file_path = event_class_dir / "config.yaml"
    config_file_path.write_text(yaml.dump(event_class_config))
