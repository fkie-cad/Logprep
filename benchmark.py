#!/usr/bin/env python3
"""
Benchmark runner for logprep-ng.

Usage:

    Run benchmark normally (stdout only, default runs: 30 30 30):

        python bench.py

    Specify custom measurement windows (seconds):

        python bench.py --runs 30 45 60

    Write full benchmark output to file (in addition to stdout):

        python bench.py --out benchmark_results.txt

    Combine both:

        python bench.py --runs 30 45 60 --out benchmark_results.txt

Notes:
- The --out flag duplicates ALL console output into the given file.
- Each run resets the docker compose stack and OpenSearch volume.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, stdev

import requests

# -------------------------
# CONFIG
# -------------------------
EVENT_NUM = 50_000
PROMETHEUS_MULTIPROC_DIR = "/tmp/logprep"

COMPOSE_DIR = Path("examples/compose")
PIPELINE_CONFIG = Path("examples/exampledata/config/ng_pipeline.yml")

GEN_INPUT_DIR = Path("./examples/exampledata/input_logdata/")
BOOTSTRAP_SERVERS = "127.0.0.1:9092"

SLEEP_AFTER_COMPOSE_UP_S = 30
SLEEP_AFTER_GENERATE_S = 2

OPENSEARCH_URL = "http://localhost:9200"
PROCESSED_INDEX = "processed"

COUNT_BEFORE_KILL = True
REFRESH_BEFORE_COUNT = True


# -------------------------
# OUTPUT TEE
# -------------------------
class Tee:
    """Duplicate writes to stdout + optional file. Minimal footprint for scripts using print()."""

    def __init__(self, primary, secondary):
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        n = self._primary.write(s)
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.write(s)
            self._secondary.flush()
        return n

    def flush(self) -> None:
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.flush()


# -------------------------
# DATA MODEL
# -------------------------
@dataclass(frozen=True)
class RunResult:
    run_seconds: int
    startup_s: float
    window_s: float
    processed: int

    @property
    def rate(self) -> float:
        return self.processed / self.window_s if self.window_s > 0 else 0.0


# -------------------------
# HELPERS
# -------------------------
def run_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    ignore_error: bool = False,
) -> None:
    try:
        subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None, env=env)
    except subprocess.CalledProcessError:
        if not ignore_error:
            raise


def popen_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env)


def kill_hard(p: subprocess.Popen) -> None:
    if p.poll() is not None:
        return
    p.kill()
    p.wait()


def opensearch_count_processed() -> int:
    if REFRESH_BEFORE_COUNT:
        requests.post(f"{OPENSEARCH_URL}/_refresh", timeout=10).raise_for_status()

    r = requests.get(f"{OPENSEARCH_URL}/{PROCESSED_INDEX}/_count", timeout=10)
    if r.status_code == 404:
        return 0
    r.raise_for_status()
    return int(r.json()["count"])


def reset_prometheus_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)


# -------------------------
# BENCH
# -------------------------
def benchmark_run(run_seconds: int) -> RunResult:
    env = os.environ.copy()
    env["PROMETHEUS_MULTIPROC_DIR"] = PROMETHEUS_MULTIPROC_DIR

    reset_prometheus_dir(PROMETHEUS_MULTIPROC_DIR)

    ng_proc: subprocess.Popen | None = None

    try:
        # compose reset + fresh opensearch volume
        run_cmd(["docker", "compose", "down"], cwd=COMPOSE_DIR, env=env)
        run_cmd(["docker", "volume", "rm", "compose_opensearch-data"], env=env, ignore_error=True)
        run_cmd(
            ["docker", "compose", "up", "-d", "kafka", "opensearch", "dashboards", "grafana"],
            cwd=COMPOSE_DIR,
            env=env,
        )

        time.sleep(SLEEP_AFTER_COMPOSE_UP_S)

        # generate events
        batch_size = max(EVENT_NUM // 10, 10)
        output_config = f'{{"bootstrap.servers": "{BOOTSTRAP_SERVERS}"}}'
        run_cmd(
            [
                "logprep",
                "generate",
                "kafka",
                "--input-dir",
                str(GEN_INPUT_DIR),
                "--batch-size",
                str(batch_size),
                "--events",
                str(EVENT_NUM),
                "--output-config",
                output_config,
            ],
            env=env,
        )

        time.sleep(SLEEP_AFTER_GENERATE_S)

        # start logprep-ng
        t0 = time.time()
        ng_proc = popen_cmd(["logprep-ng", "run", str(PIPELINE_CONFIG)], env=env)
        startup_s = time.time() - t0

        # measurement window
        t_run = time.time()
        time.sleep(run_seconds)
        window_s = time.time() - t_run

        if COUNT_BEFORE_KILL:
            processed = opensearch_count_processed()
            kill_hard(ng_proc)
            ng_proc = None
        else:
            kill_hard(ng_proc)
            ng_proc = None
            processed = opensearch_count_processed()

        return RunResult(
            run_seconds=run_seconds,
            startup_s=startup_s,
            window_s=window_s,
            processed=processed,
        )

    finally:
        if ng_proc is not None:
            kill_hard(ng_proc)
        run_cmd(["docker", "compose", "down"], cwd=COMPOSE_DIR, env=env)


# -------------------------
# REPORTING
# -------------------------
def print_runs_table_and_summary(results: list[RunResult]) -> None:
    if not results:
        print("(no runs)")
        return

    rates = [r.rate for r in results]
    processed_counts = [r.processed for r in results]
    window_times = [r.window_s for r in results]
    startups = [r.startup_s for r in results]

    total_processed = sum(processed_counts)
    total_runtime = sum(window_times)
    weighted_rate = total_processed / total_runtime if total_runtime > 0 else 0.0

    avg_rate = mean(rates)
    med_rate = median(rates)
    min_rate = min(rates)
    max_rate = max(rates)
    sd_rate = stdev(rates) if len(rates) >= 2 else 0.0

    headers = ["run_s", "window_s", "startup_s", "processed", "docs/s"]
    rows: list[list[str]] = []
    for r in results:
        rows.append(
            [
                f"{r.run_seconds}",
                f"{r.window_s:.3f}",
                f"{r.startup_s:.3f}",
                f"{r.processed:,}".replace(",", "_"),
                f"{r.rate:,.2f}",
            ]
        )

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(cells[i].rjust(col_widths[i]) for i in range(len(cells))) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    print("\n=== RUNS TABLE ===")
    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)

    print("\n=== FINAL BENCHMARK SUMMARY ===")
    print(f"runs:                  {len(results)}")
    print(f"total runtime:         {total_runtime:.3f} s")
    print(f"total processed:       {total_processed:,}".replace(",", "_"))
    print("")
    print(f"throughput (weighted): {weighted_rate:,.2f} docs/s   <-- primary")
    print(f"throughput (median):   {med_rate:,.2f} docs/s")
    print(f"throughput (average):  {avg_rate:,.2f} docs/s")
    print(f"throughput (min/max):  {min_rate:,.2f} / {max_rate:,.2f} docs/s")
    print(f"throughput (std dev):  {sd_rate:,.2f} docs/s")
    print("")
    print(f"startup avg:           {mean(startups):.3f} s")
    print("================================")


def print_single_run_result(r: RunResult) -> None:
    print("--- RESULT ---")
    print(f"run_seconds:            {r.run_seconds}")
    print(f"events generated:       {EVENT_NUM:_}")
    print(f"startup time:           {r.startup_s:.3f} s")
    print(f"measurement window:     {r.window_s:.3f} s")
    print(f"processed (OpenSearch): {r.processed:_}")
    print(f"throughput:             {r.rate:,.2f} docs/s")
    print("--------------")


# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run logprep-ng benchmark suite.")

    p.add_argument(
        "--runs",
        type=int,
        nargs="+",
        default=[30, 30, 30],
        help=(
            "Measurement windows in seconds.\n"
            "Example:\n"
            "  python bench.py --runs 30 45 60\n\n"
            "Default:\n"
            "  30 30 30"
        ),
    )

    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Duplicate console output into file (e.g. --out benchmark_results.txt)",
    )

    args = p.parse_args()

    if any(r <= 0 for r in args.runs):
        p.error("--runs must contain positive integers (seconds).")

    return args


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    args = parse_args()

    file_handle = None
    old_stdout = sys.stdout
    try:
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            file_handle = args.out.open("w", encoding="utf-8")
            sys.stdout = Tee(old_stdout, file_handle)  # type: ignore[assignment]

        benchmark_seconds = tuple(args.runs)
        print(f"Start benchmarking: run {benchmark_seconds=}")

        results: list[RunResult] = []

        for i, seconds in enumerate(benchmark_seconds, start=1):
            print(f"----- Run Round {i}: {seconds} seconds -----")
            r = benchmark_run(run_seconds=seconds)
            results.append(r)
            print_single_run_result(r)
            print()

        print_runs_table_and_summary(results)

    finally:
        sys.stdout = old_stdout
        if file_handle is not None:
            file_handle.close()
