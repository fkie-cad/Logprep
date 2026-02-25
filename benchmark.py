"""
Benchmark runner for logprep-ng.

Usage:

    Run benchmark normally (stdout only, default runs: 30 30 30):

        python benchmark.py

    Specify custom measurement windows (seconds):

        python benchmark.py --runs 30 45 60

    Write full benchmark output to file (in addition to stdout):

        python benchmark.py --out benchmark_results.txt

    Combine both:

        python benchmark.py --runs 30 45 60 --out benchmark_results.txt

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
    """File-like object that duplicates writes to a primary stream and an
    optional secondary stream."""

    def __init__(self, primary, secondary):
        """
        Create a Tee stream.

        Args:
            primary: Stream to write to (typically sys.stdout).
            secondary: Optional stream to duplicate writes into (e.g. open file handle).
        """
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        """Write to primary stream and duplicate to secondary stream (if any)."""
        n = self._primary.write(s)
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.write(s)
            self._secondary.flush()
        return n

    def flush(self) -> None:
        """Flush both primary and secondary streams."""
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.flush()


# -------------------------
# DATA MODEL
# -------------------------
@dataclass(frozen=True)
class RunResult:
    """Result of a single benchmark run."""

    run_seconds: int
    startup_s: float
    window_s: float
    processed: int

    @property
    def rate(self) -> float:
        """Documents per second processed during the measurement window."""
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
    """
    Run a command and raise on non-zero exit code unless ignore_error is True.

    Args:
        cmd: Command and args.
        cwd: Optional working directory.
        env: Optional environment.
        ignore_error: If True, ignore non-zero exit codes.
    """
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
    """
    Start a subprocess without waiting.

    Args:
        cmd: Command and args.
        cwd: Optional working directory.
        env: Optional environment.

    Returns:
        subprocess.Popen handle.
    """
    return subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env)


def kill_hard(proc: subprocess.Popen) -> None:
    """
    Hard-kill a process (SIGKILL on Unix) to avoid shutdown flushing side effects.

    Args:
        proc: Process handle.
    """
    if proc.poll() is not None:
        return
    proc.kill()
    proc.wait()


def opensearch_count_processed() -> int:
    """
    Return the count of documents in the processed index.

    Returns 0 if the index does not exist yet (404).

    Returns:
        Document count as int.
    """
    if REFRESH_BEFORE_COUNT:
        requests.post(f"{OPENSEARCH_URL}/_refresh", timeout=10).raise_for_status()

    resp = requests.get(f"{OPENSEARCH_URL}/{PROCESSED_INDEX}/_count", timeout=10)
    if resp.status_code == 404:
        return 0
    resp.raise_for_status()
    return int(resp.json()["count"])


def reset_prometheus_dir(path: str) -> None:
    """
    Reset PROMETHEUS_MULTIPROC_DIR on disk (delete + recreate).

    Args:
        path: Directory path.
    """
    shutil.rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)


# -------------------------
# BENCH
# -------------------------
def benchmark_run(run_seconds: int) -> RunResult:
    """
    Execute a single benchmark run:
    - reset compose + volume
    - generate events to Kafka
    - start local logprep-ng
    - sleep measurement window
    - count docs in OpenSearch
    - SIGKILL logprep-ng to avoid flush
    - tear down compose

    Args:
        run_seconds: Measurement window length in seconds.

    Returns:
        RunResult for this run.
    """
    env = os.environ.copy()
    env["PROMETHEUS_MULTIPROC_DIR"] = PROMETHEUS_MULTIPROC_DIR

    reset_prometheus_dir(PROMETHEUS_MULTIPROC_DIR)

    ng_proc: subprocess.Popen | None = None

    try:
        run_cmd(["docker", "compose", "down"], cwd=COMPOSE_DIR, env=env)
        run_cmd(["docker", "volume", "rm", "compose_opensearch-data"], env=env, ignore_error=True)
        run_cmd(
            ["docker", "compose", "up", "-d", "kafka", "opensearch", "dashboards", "grafana"],
            cwd=COMPOSE_DIR,
            env=env,
        )

        time.sleep(SLEEP_AFTER_COMPOSE_UP_S)

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

        t0 = time.time()
        ng_proc = popen_cmd(["logprep-ng", "run", str(PIPELINE_CONFIG)], env=env)
        startup_s = time.time() - t0

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
def _render_ascii_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Render a compact ASCII table.

    Args:
        headers: Column headers.
        rows: Table rows as strings.

    Returns:
        Rendered table as a single string.
    """
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return "| " + " | ".join(cells[i].rjust(col_widths[i]) for i in range(len(cells))) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    lines: list[str] = [sep, fmt_row(headers), sep]
    for row in rows:
        lines.append(fmt_row(row))
    lines.append(sep)
    return "\n".join(lines)


def print_runs_table_and_summary(run_results: list[RunResult]) -> None:
    """
    Print an ASCII table for all runs plus a summary block.

    Args:
        run_results: List of RunResult objects.
    """
    if not run_results:
        print("(no runs)")
        return

    rates = [res.rate for res in run_results]
    processed_counts = [res.processed for res in run_results]
    window_times = [res.window_s for res in run_results]
    startups = [res.startup_s for res in run_results]

    total_processed = sum(processed_counts)
    total_runtime = sum(window_times)

    throughput = {
        "weighted": total_processed / total_runtime if total_runtime > 0 else 0.0,
        "average": mean(rates),
        "median": median(rates),
        "min": min(rates),
        "max": max(rates),
        "std_dev": stdev(rates) if len(rates) >= 2 else 0.0,
    }

    # Std dev as percent of average throughput (coefficient of variation)
    throughput["std_dev_pct_avg"] = (
        throughput["std_dev"] / throughput["average"] * 100 if throughput["average"] > 0 else 0.0
    )

    # Optional: also as percent of weighted throughput (often more meaningful)
    throughput["std_dev_pct_weighted"] = (
        throughput["std_dev"] / throughput["weighted"] * 100 if throughput["weighted"] > 0 else 0.0
    )

    headers = ["run_s", "window_s", "startup_s", "processed", "docs/s"]
    rows: list[list[str]] = [
        [
            f"{res.run_seconds}",
            f"{res.window_s:.3f}",
            f"{res.startup_s:.3f}",
            f"{res.processed:,}".replace(",", "_"),
            f"{res.rate:,.2f}",
        ]
        for res in run_results
    ]

    print("\n=== RUNS TABLE ===")
    print(_render_ascii_table(headers, rows))

    print("\n=== FINAL BENCHMARK SUMMARY ===")
    print(f"runs:                  {len(run_results)}")
    print(f"total runtime:         {total_runtime:.3f} s")
    print(f"total processed:       {total_processed:,}".replace(",", "_"))
    print("")
    print(f"throughput (weighted): {throughput['weighted']:,.2f} docs/s   <-- primary")
    print(f"throughput (median):   {throughput['median']:,.2f} docs/s")
    print(f"throughput (average):  {throughput['average']:,.2f} docs/s")
    print(f"throughput (min/max):  {throughput['min']:,.2f} / {throughput['max']:,.2f} docs/s")
    print(f"throughput (std dev):  {throughput['std_dev']:,.2f} docs/s")
    print(f"throughput (variance): {throughput['std_dev_pct_weighted']:.2f}% of weighted")
    print("")
    print(f"startup avg:           {mean(startups):.3f} s")
    print("================================")


def print_single_run_result(run_result: RunResult) -> None:
    """
    Print the result block for a single run.

    Args:
        run_result: RunResult.
    """
    print("--- RESULT ---")
    print(f"run_seconds:            {run_result.run_seconds}")
    print(f"events generated:       {EVENT_NUM:_}")
    print(f"startup time:           {run_result.startup_s:.3f} s")
    print(f"measurement window:     {run_result.window_s:.3f} s")
    print(f"processed (OpenSearch): {run_result.processed:_}")
    print(f"throughput:             {run_result.rate:,.2f} docs/s")
    print("--------------")


# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    """
    Parse CLI args.

    Returns:
        argparse.Namespace
    """
    parser = argparse.ArgumentParser(description="Run logprep-ng benchmark suite.")

    parser.add_argument(
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

    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Duplicate console output into file (e.g. --out benchmark_results.txt)",
    )

    cli_args = parser.parse_args()

    if any(r <= 0 for r in cli_args.runs):
        parser.error("--runs must contain positive integers (seconds).")

    return cli_args


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
        print(f"Start benchmarking: benchmark_seconds={benchmark_seconds}")

        results: list[RunResult] = []

        for run_idx, seconds in enumerate(benchmark_seconds, start=1):
            print(f"----- Run Round {run_idx}: {seconds} seconds -----")
            result = benchmark_run(run_seconds=seconds)
            results.append(result)
            print_single_run_result(result)
            print()

        print_runs_table_and_summary(results)

    finally:
        sys.stdout = old_stdout
        if file_handle is not None:
            file_handle.close()
