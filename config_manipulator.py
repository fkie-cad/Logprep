import sys
import time
from pathlib import Path

from ruamel.yaml import YAML


def set_yaml_value(file_path: Path, key: str, value) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 10_000

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    old_value = data.get(key, "<not set>")
    data[key] = value

    print(f"Updated '{key}': {old_value} -> {value}")

    with file_path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


if __name__ == "__main__":
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    if delay > 0:
        print(f"Sleeping for {delay} seconds...")
        time.sleep(delay)

    config_path = Path("examples/exampledata/config/_benchmark_ng_pipeline.yml")

    set_yaml_value(config_path, "version", 3)
