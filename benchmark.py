# pylint: disable=C0103

"""
Benchmark runner for logprep (logprep-ng and non-ng).

Usage:

    python benchmark.py
    python benchmark.py --runs 30 45 60
    python benchmark.py --runs 30 45 60 --out benchmark_results.txt
    python benchmark.py --runs 30 45 60 --services kafka opensearch

Use --help to see all available configuration options.
"""

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

import requests

# -------------------------
# GLOBAL SHUTDOWN STATE
# -------------------------
_shutdown_requested: bool = False
_current_logprep_proc: subprocess.Popen | None = None
_current_compose_dir: Path | None = None
_current_env: dict[str, str] | None = None


def _handle_sigint(signum, frame):
    """
    Handle Ctrl+C (SIGINT) and perform graceful shutdown.
    """
    global _shutdown_requested
    _shutdown_requested = True

    print("\n\n⚠ Ctrl+C detected. Shutting down benchmark...")

    if _current_logprep_proc is not None:
        try:
            kill_hard(_current_logprep_proc)
        except Exception:
            pass

    if _current_compose_dir is not None and _current_env is not None:
        try:
            run_cmd(
                ["docker", "compose", "down"],
                cwd=_current_compose_dir,
                env=_current_env,
                ignore_error=True,
            )
        except Exception:
            pass

    sys.exit(130)


# -------------------------
# OUTPUT TEE
# -------------------------
class Tee:
    """Duplicate stdout into an optional second stream."""

    def __init__(self, primary, secondary):
        """Initialize with primary and optional secondary stream."""
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:
        """Write to both streams."""
        n = self._primary.write(s)
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.write(s)
            self._secondary.flush()
        return n

    def flush(self) -> None:
        """Flush both streams."""
        self._primary.flush()
        if self._secondary is not None:
            self._secondary.flush()


# -------------------------
# DATA MODEL
# -------------------------
@dataclass(frozen=True)
class RunResult:
    """Single benchmark run result."""

    run_seconds: int
    startup_s: float
    window_s: float
    processed: int

    @property
    def rate(self) -> float:
        """Processed documents per second."""
        return self.processed / self.window_s if self.window_s > 0 else 0.0


# -------------------------
# METADATA PRINT
# -------------------------
def print_benchmark_config(args: argparse.Namespace) -> None:
    """
    Print the current benchmark configuration including environment metadata.

    Args:
        args: Parsed CLI arguments namespace.
    """
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)

    print("\n=== BENCHMARK CONFIGURATION ===")
    print(f"{'timestamp (local)':30s}: {now_local.isoformat()}")
    print(f"{'timestamp (UTC)':30s}: {now_utc.isoformat()}")
    print(f"{'python version':30s}: {sys.version.split()[0]}")
    print("-" * 40)

    args_dict = vars(args).copy()

    for key in sorted(args_dict):
        value = args_dict[key]

        # Format integers with underscore separator
        if isinstance(value, int):
            formatted = f"{value:_}"

        # Format list of integers (e.g. runs)
        elif isinstance(value, list) and all(isinstance(v, int) for v in value):
            formatted = "[" + ", ".join(f"{v:_}" for v in value) + "]"

        else:
            formatted = value

        print(f"{key:30s}: {formatted}")

        if key == "ng":
            pipeline_config = resolve_pipeline_config(args.ng)
            mode = "logprep-ng" if args.ng == 1 else "logprep"
            print(f"{'  ↳ mode':30s}: {mode}")
            print(f"{'  ↳ pipeline_config':30s}: {pipeline_config}")

    print("================================\n")


def print_single_run_result(run_result: RunResult, *, event_num: int) -> None:
    """
    Print the result block for a single run.

    Args:
        run_result: RunResult.
        event_num: Number of generated events.
    """
    print("--- RESULT ---")
    print(f"run_seconds:            {run_result.run_seconds:_}")
    print(f"events generated:       {event_num:_}")
    print(f"startup time:           {run_result.startup_s:.3f} s")
    print(f"measurement window:     {run_result.window_s:.3f} s")
    print(f"processed (OpenSearch): {run_result.processed:_}")
    print(f"throughput:             {run_result.rate:,.2f} docs/s")
    print("--------------")


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
    Run a command and optionally ignore non-zero exit codes.

    Args:
        cmd: Command and arguments.
        cwd: Optional working directory.
        env: Optional environment variables.
        ignore_error: Suppress CalledProcessError if True.
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
        cmd: Command and arguments.
        cwd: Optional working directory.
        env: Optional environment variables.

    Returns:
        subprocess.Popen handle.
    """
    return subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        start_new_session=True,
    )


def kill_hard(proc: subprocess.Popen) -> None:
    """
    Forcefully terminate a process.

    Args:
        proc: Process handle.
    """
    if proc.poll() is not None:
        return

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    proc.wait()


def opensearch_refresh(opensearch_url: str, processed_index: str) -> None:
    """
    Force a refresh of the processed index so counts reflect recent writes.

    Args:
        opensearch_url: OpenSearch base URL.
        processed_index: Index name to refresh.
    """
    resp = requests.post(f"{opensearch_url}/{processed_index}/_refresh", timeout=10)
    if resp.status_code == 404:
        return
    resp.raise_for_status()


def opensearch_count_processed(opensearch_url: str, processed_index: str) -> int:
    """
    Return document count of the processed index.

    Args:
        opensearch_url: OpenSearch base URL.
        processed_index: Index name to query.

    Returns:
        Document count as integer.
    """
    resp = requests.get(f"{opensearch_url}/{processed_index}/_count", timeout=10)
    if resp.status_code == 404:
        return 0
    resp.raise_for_status()
    return int(resp.json()["count"])


def reset_prometheus_dir(path: str) -> None:
    """
    Recreate PROMETHEUS_MULTIPROC_DIR.

    Args:
        path: Directory path.
    """
    shutil.rmtree(path, ignore_errors=True)
    Path(path).mkdir(parents=True, exist_ok=True)


def resolve_pipeline_config(ng: int) -> Path:
    """
    Return pipeline config for selected mode.

    Args:
        ng: 1 for logprep-ng, 0 for logprep.

    Returns:
        Pipeline config path.
    """
    if ng == 1:
        return Path("./examples/exampledata/config/ng_pipeline.yml")
    return Path("./examples/exampledata/config/pipeline.yml")


def read_vm_max_map_count() -> int:
    """
    Read current vm.max_map_count from /proc.

    Returns:
        Current vm.max_map_count as integer.
    """
    try:
        return int(Path("/proc/sys/vm/max_map_count").read_text(encoding="utf-8").strip())
    except Exception:
        return -1


def ensure_vm_max_map_count(min_value: int = 262144) -> None:
    """
    Ensure vm.max_map_count is at least the given minimum value.

    Args:
        min_value: Minimum required vm.max_map_count.

    Raises:
        RuntimeError if vm.max_map_count is too low.
    """
    current = read_vm_max_map_count()
    if current == -1:
        return
    if current < min_value:
        raise RuntimeError(
            f"vm.max_map_count is {current}, but must be at least {min_value} for OpenSearch.\n"
            f"Run: sudo sysctl -w vm.max_map_count={min_value}"
        )


def wait_for_tcp(host: str, port: int, *, timeout_s: float, interval_s: float = 0.5) -> None:
    """
    Wait until a TCP service accepts connections.

    Args:
        host: Hostname or IP.
        port: TCP port.
        timeout_s: Total timeout in seconds.
        interval_s: Poll interval in seconds.
    """
    deadline = time.time() + timeout_s
    last_err: OSError | None = None

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError as e:
            last_err = e
            time.sleep(interval_s)

    raise TimeoutError(f"TCP service not ready: {host}:{port} (last error: {last_err})")


def wait_for_opensearch(opensearch_url: str, *, timeout_s: float, interval_s: float = 0.5) -> None:
    """
    Wait until OpenSearch responds with a successful HTTP status.

    Args:
        opensearch_url: OpenSearch base URL.
        timeout_s: Total timeout in seconds.
        interval_s: Poll interval in seconds.
    """
    deadline = time.time() + timeout_s
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            resp = requests.get(f"{opensearch_url}/_cluster/health", timeout=2)
            if resp.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(interval_s)

    raise TimeoutError(f"OpenSearch not ready: {opensearch_url} (last error: {last_err})")


def wait_for_kafka_topic(
    host: str, port: int, topic: str, *, timeout_s: float, interval_s: float = 0.5
) -> None:
    """
    Wait until Kafka responds to topic describe for a given topic.

    Args:
        host: Kafka host.
        port: Kafka port.
        topic: Topic name to describe.
        timeout_s: Total timeout in seconds.
        interval_s: Poll interval in seconds.
    """
    deadline = time.time() + timeout_s
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    "kafka",
                    "kafka-topics.sh",
                    "--bootstrap-server",
                    f"{host}:{port}",
                    "--topic",
                    topic,
                    "--describe",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode == 0:
                return
            last_err = RuntimeError(proc.stderr.strip() or proc.stdout.strip())
        except Exception as e:
            last_err = e
        time.sleep(interval_s)

    raise TimeoutError(f"Kafka not ready (topic '{topic}' not describable). Last error: {last_err}")


def compose_config_services(
    *,
    compose_dir: Path,
    env: dict[str, str],
) -> list[str]:
    """
    Return all services defined in the docker compose project.

    Args:
        compose_dir: Docker compose directory.
        env: Environment variables.

    Returns:
        Service names as a list of strings.
    """
    proc = subprocess.run(
        ["docker", "compose", "config", "--services"],
        check=True,
        cwd=str(compose_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def stop_unwanted_services(
    *,
    compose_dir: Path,
    env: dict[str, str],
    wanted: list[str],
) -> None:
    """
    Stop any services not included in the wanted list.

    Args:
        compose_dir: Docker compose directory.
        env: Environment variables.
        wanted: Services that should remain running.
    """
    all_services = compose_config_services(compose_dir=compose_dir, env=env)
    unwanted = [s for s in all_services if s not in set(wanted)]
    if not unwanted:
        return

    run_cmd(["docker", "compose", "stop", *unwanted], cwd=compose_dir, env=env, ignore_error=True)
    run_cmd(
        ["docker", "compose", "rm", "-f", *unwanted], cwd=compose_dir, env=env, ignore_error=True
    )


# -------------------------
# BENCH
# -------------------------
def benchmark_run(
    run_seconds: int,
    *,
    ng: int,
    event_num: int,
    prometheus_multiproc_dir: str,
    compose_dir: Path,
    pipeline_config: Path,
    gen_input_dir: Path,
    bootstrap_servers: str,
    sleep_after_compose_up_s: int,
    sleep_after_generate_s: int,
    sleep_after_logprep_start_s: int,
    opensearch_url: str,
    processed_index: str,
    services: list[str],
) -> RunResult:
    """
    Execute one benchmark run.

    Args:
        run_seconds: Measurement window length.
        ng: 1 for logprep-ng, 0 for logprep.
        event_num: Number of events to generate.
        prometheus_multiproc_dir: Metrics directory.
        compose_dir: Docker compose directory.
        pipeline_config: Pipeline configuration file.
        gen_input_dir: Generator input directory (shared for ng and non-ng).
        bootstrap_servers: Kafka bootstrap.servers value.
        sleep_after_compose_up_s: Sleep after compose up.
        sleep_after_generate_s: Sleep after generation.
        sleep_after_logprep_start_s: Warmup sleep before measurement.
        opensearch_url: OpenSearch base URL.
        processed_index: Index to count.
        services: Docker compose services to start (teardown uses compose down).

    Returns:
        RunResult for this run.
    """
    env = os.environ.copy()
    env["PROMETHEUS_MULTIPROC_DIR"] = prometheus_multiproc_dir

    reset_prometheus_dir(prometheus_multiproc_dir)

    logprep_proc: subprocess.Popen | None = None

    global _current_logprep_proc, _current_compose_dir, _current_env
    _current_compose_dir = compose_dir
    _current_env = env

    try:
        ensure_vm_max_map_count()

        run_cmd(["docker", "compose", "down"], cwd=compose_dir, env=env)
        run_cmd(["docker", "volume", "rm", "compose_opensearch-data"], env=env, ignore_error=True)

        run_cmd(
            ["docker", "compose", "up", "-d", "--no-deps", *services],
            cwd=compose_dir,
            env=env,
        )

        stop_unwanted_services(compose_dir=compose_dir, env=env, wanted=services)

        if "kafka" in set(services):
            wait_for_tcp("127.0.0.1", 9092, timeout_s=float(sleep_after_compose_up_s))
            wait_for_kafka_topic(
                "127.0.0.1", 9092, "consumer", timeout_s=float(sleep_after_compose_up_s)
            )

        if "opensearch" in set(services):
            wait_for_tcp("127.0.0.1", 9200, timeout_s=float(sleep_after_compose_up_s))
            wait_for_opensearch(opensearch_url, timeout_s=float(sleep_after_compose_up_s))

        batch_size = max(event_num // 10, 10)
        output_config = f'{{"bootstrap.servers": "{bootstrap_servers}"}}'

        run_cmd(
            [
                "logprep",
                "generate",
                "kafka",
                "--input-dir",
                str(gen_input_dir),
                "--batch-size",
                str(batch_size),
                "--events",
                str(event_num),
                "--output-config",
                output_config,
            ],
            env=env,
        )

        time.sleep(sleep_after_generate_s)

        binary = "logprep-ng" if ng == 1 else "logprep"

        t_startup = time.time()
        logprep_proc = popen_cmd([binary, "run", str(pipeline_config)], env=env)
        _current_logprep_proc = logprep_proc

        time.sleep(sleep_after_logprep_start_s)

        baseline = opensearch_count_processed(opensearch_url, processed_index)
        startup_s = time.time() - t_startup

        t_run = time.time()
        time.sleep(run_seconds)
        window_s = time.time() - t_run

        kill_hard(logprep_proc)
        logprep_proc = None
        _current_logprep_proc = None

        # ensure near-real-time writes are visible to _count before measuring
        opensearch_refresh(opensearch_url, processed_index)

        after = opensearch_count_processed(opensearch_url, processed_index)
        processed = max(0, after - baseline)

        return RunResult(
            run_seconds=run_seconds, startup_s=startup_s, window_s=window_s, processed=processed
        )

    finally:
        if logprep_proc is not None:
            kill_hard(logprep_proc)
        _current_logprep_proc = None
        run_cmd(["docker", "compose", "down"], cwd=compose_dir, env=env, ignore_error=True)


# -------------------------
# REPORTING
# -------------------------
def print_runs_table_and_summary(run_results: list[RunResult]) -> None:
    """
    Print run table and aggregated throughput statistics.

    Args:
        run_results: List of benchmark results.
    """
    if not run_results:
        print("(no runs)")
        return

    rates = [r.rate for r in run_results]
    total_processed = sum(r.processed for r in run_results)
    total_runtime = sum(r.window_s for r in run_results)

    weighted = total_processed / total_runtime if total_runtime > 0 else 0.0

    print("\n=== FINAL BENCHMARK SUMMARY ===")
    print(f"runs:                  {len(run_results)}")
    print(f"total runtime:         {total_runtime:.3f} s")
    print(f"total processed:       {total_processed:_}")
    print("")
    print(f"throughput (weighted): {weighted:,.2f} docs/s")
    print(f"throughput (median):   {median(rates):,.2f} docs/s")
    print(f"throughput (average):  {mean(rates):,.2f} docs/s")
    print(f"throughput (min/max):  {min(rates):,.2f} / {max(rates):,.2f} docs/s")
    print(f"throughput (std dev):  {stdev(rates) if len(rates) >= 2 else 0.0:,.2f} docs/s")
    print("================================")


# -------------------------
# CLI
# -------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Run logprep benchmark suite (logprep-ng and non-ng)."
    )

    parser.add_argument(
        "--runs",
        type=int,
        nargs="+",
        default=[30, 30, 30],
        help="Measurement window durations in seconds (one value per run).",
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional file path to tee benchmark output into.",
    )

    parser.add_argument(
        "--ng",
        type=int,
        choices=(0, 1),
        default=1,
        help="Select implementation: 1 = logprep-ng, 0 = logprep.",
    )

    parser.add_argument(
        "--event-num",
        type=int,
        default=50_000,
        help="Number of events generated per run.",
    )

    parser.add_argument(
        "--prometheus-multiproc-dir",
        type=str,
        default="/tmp/logprep",
        help="PROMETHEUS_MULTIPROC_DIR used for metrics.",
    )

    parser.add_argument(
        "--compose-dir",
        type=Path,
        default=Path("examples/compose"),
        help="Directory containing the docker-compose project.",
    )

    parser.add_argument(
        "--bootstrap-servers",
        type=str,
        default="127.0.0.1:9092",
        help="Kafka bootstrap.servers value for event generation.",
    )

    parser.add_argument(
        "--sleep-after-compose-up-s",
        type=int,
        default=30,
        help="Seconds to wait after docker compose up before proceeding.",
    )

    parser.add_argument(
        "--sleep-after-generate-s",
        type=int,
        default=2,
        help="Seconds to wait after event generation completes.",
    )

    parser.add_argument(
        "--sleep-after-logprep-start-s",
        type=int,
        default=5,
        help="Warmup time in seconds before measurement window starts.",
    )

    parser.add_argument(
        "--opensearch-url",
        type=str,
        default="http://localhost:9200",
        help="Base URL of the OpenSearch instance.",
    )

    parser.add_argument(
        "--processed-index",
        type=str,
        default="processed",
        help="OpenSearch index name used to count processed documents.",
    )

    parser.add_argument(
        "--services",
        type=str,
        nargs="+",
        default=["kafka", "opensearch"],
        help="Docker compose services to start (others will be stopped).",
    )

    parser.add_argument(
        "--gen-input-dir",
        type=Path,
        default=Path("./examples/exampledata/kafka_generate_input_logdata/"),
        help="Input directory for logprep generate kafka (shared for ng and non-ng).",
    )

    return parser


def parse_args() -> argparse.Namespace:
    """Parse and validate CLI arguments."""
    parser = build_arg_parser()
    args = parser.parse_args()

    if any(r <= 0 for r in args.runs):
        parser.error("--runs must contain positive integers.")

    if not args.services:
        parser.error("--services must contain at least one service name.")

    return args


def setup_output_tee(out_path: Path | None) -> None:
    """
    Redirect stdout into a tee that also writes into a file (if requested).

    Args:
        out_path: Optional output file path for a copy of stdout.
    """
    if out_path is None:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    f = out_path.open("w", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, f)  # type: ignore[assignment]


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_sigint)

    args_ = parse_args()
    setup_output_tee(args_.out)

    print_benchmark_config(args_)

    pipeline_config_ = resolve_pipeline_config(args_.ng)

    results: list[RunResult] = []

    benchmark_seconds = args_.runs
    for run_idx, seconds in enumerate(benchmark_seconds, start=1):
        print(f"----- Run Round {run_idx}: {seconds} seconds -----")
        result = benchmark_run(
            run_seconds=seconds,
            ng=args_.ng,
            event_num=args_.event_num,
            prometheus_multiproc_dir=args_.prometheus_multiproc_dir,
            compose_dir=args_.compose_dir,
            pipeline_config=pipeline_config_,
            gen_input_dir=args_.gen_input_dir,
            bootstrap_servers=args_.bootstrap_servers,
            sleep_after_compose_up_s=args_.sleep_after_compose_up_s,
            sleep_after_generate_s=args_.sleep_after_generate_s,
            sleep_after_logprep_start_s=args_.sleep_after_logprep_start_s,
            opensearch_url=args_.opensearch_url,
            processed_index=args_.processed_index,
            services=args_.services,
        )
        results.append(result)
        print_single_run_result(result, event_num=args_.event_num)
        print()

    print_runs_table_and_summary(results)
