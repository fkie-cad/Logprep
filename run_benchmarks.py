#!/usr/bin/env python3

import subprocess
import sys
from datetime import datetime
from pathlib import Path

PYTHON_VERSIONS = ["3.11"]  # , "3.12", "3.13", "3.14"]
MODES = [
    ("nonNG", "0"),
    ("asyncNG", "1"),
]


def run_benchmarks() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("benchmark_results") / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Results directory: {out_dir}\n")

    commands = []

    for mode_name, ng_flag in MODES:
        for py in PYTHON_VERSIONS:
            outfile = out_dir / f"{mode_name}_python{py}.txt"

            cmd = [
                "uv",
                "run",
                "--python",
                py,
                "benchmark.py",
                "--event-num",
                "120000",
                "--runs",
                "30",
                "--ng",
                ng_flag,
                "--out",
                str(outfile),
            ]

            commands.append(cmd)

    for i, cmd in enumerate(commands, start=1):
        print(f"=== Run {i}/{len(commands)} ===")
        print(" ".join(cmd))

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Run failed with exit code {e.returncode}")
            sys.exit(e.returncode)

    print("\nAll benchmark runs finished.")


if __name__ == "__main__":
    run_benchmarks()
