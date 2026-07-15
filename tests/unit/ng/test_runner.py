# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

"""Tests for Runner.run()"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from unittest.mock import AsyncMock, NonCallableMagicMock, patch

import pytest

from logprep.ng.manager import PipelineManager
from logprep.ng.runner import Runner
from logprep.ng.util.config_refresh import StopConfigRefresh
from logprep.ng.util.configuration import Configuration, MetricsConfig


@dataclass
class WithArgs:
    fn: Callable


async def block_until_event(event: asyncio.Event, *_, **__):
    await event.wait()


BLOCK_UNTIL_EVENT = WithArgs(block_until_event)


def mock_sequence(*sequence: object):
    """
    Build an async side_effect from a declarative sequence.

      - asyncio.Event  → await it, then continue
      - WithArgs(fn)   → call fn(*args, **kwargs); await if coroutine; return the result
      - callable       → call it; if the result is a coroutine, await it; then continue
      - Exception inst → raise it
      - any other obj  → return it
    """
    seq = list(sequence)

    async def _impl(*args, **kwargs):
        while seq:
            elem = seq.pop(0)
            match elem:
                case Exception():
                    raise elem
                case WithArgs(fn=fn):
                    result = fn(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    return result  # terminal
                case elem if callable(elem):
                    result = elem()
                    if asyncio.iscoroutine(result):
                        await result
                case object():
                    return elem
        raise AssertionError("mock_sequence exhausted: called more times than declared")

    return _impl


def async_side_effects(*funcs: Callable[..., Coroutine]):
    """
    Test utility for async mocks to support multiple invocations with different code paths.

    ```
    async def handler1(): ...
    async def handler2(): ...

    some_mocked_func.side_effect = async_side_effects(handler1, handler2)

    await some_mocked_func() # calls handler1
    await some_mocked_func() # calls handler2
    ```
    """
    seq = iter(funcs)

    async def _call(*args, **kwargs):
        next_func = next(seq)
        result = next_func(*args, **kwargs)
        assert asyncio.iscoroutine(result)
        return await result

    return _call


MODULE = "logprep.ng.runner"
CONFIG_REFRESH = f"{MODULE}.wait_for_refreshed_config"
GETTER_REFRESH = f"{MODULE}.RefreshableGetter.refresh"
PIPELINE_MANAGER = f"{MODULE}.PipelineManager"


def make_config(
    *,
    version: str = "v1",
    config_refresh_interval: float | None = 1.0,
    getter_refresh_interval: float = 0.0,
    graceful_orchestrator_timeout: float = 5.0,
    graceful_worker_timeout: float = 5.0,
    hard_orchestrator_timeout: float = 5.0,
    metrics_enabled: bool = False,
) -> NonCallableMagicMock:
    cfg = NonCallableMagicMock(spec=Configuration)
    cfg.version = version
    cfg.config_refresh_interval = config_refresh_interval
    cfg.refreshable_getter_base_interval_s = getter_refresh_interval
    cfg.graceful_orchestrator_shutdown_timeout_s = graceful_orchestrator_timeout
    cfg.graceful_worker_shutdown_timeout_s = graceful_worker_timeout
    cfg.hard_orchestrator_shutdown_timeout_s = hard_orchestrator_timeout
    cfg.metrics = MetricsConfig(enabled=metrics_enabled)
    cfg.reload = AsyncMock()
    return cfg


def mock_config_refresh(
    *sequence: WithArgs | Exception | Callable | Configuration, regular_behavior: bool = True
):
    """
    Declarative mock factory for `wait_for_config_refresh`.
    The standard lifecycle entails waiting for the externally provided event and raising a
    `StopConfigRefresh` exception afterwards.
    """
    expanded = [*sequence]
    if regular_behavior:
        expanded.append(BLOCK_UNTIL_EVENT)
        expanded.append(StopConfigRefresh("stop_event set"))
    return mock_sequence(*expanded)


def mock_pipeline_run(*sequence: WithArgs | Exception | Callable, regular_behavior: bool = True):
    """
    Declarative mock factory for `PipelineManager.run`.
    The standard lifecycle entails blocking on the stop_event passed in by
    `StoppableTask` until the pipeline is signalled to stop.
    """
    expanded = [*sequence]
    if regular_behavior:
        expanded.append(BLOCK_UNTIL_EVENT)
    return mock_sequence(*expanded)


async def run_until_exception(runner: Runner) -> Exception | None:
    try:
        await runner.run()
        return None
    except Exception as exc:
        if isinstance(exc, ExceptionGroup):
            return exc.exceptions[0]
        return exc


async def stop_runner_after(runner: Runner, event: asyncio.Event, wait: float = 0.0) -> None:
    await event.wait()
    await asyncio.sleep(wait)
    runner.stop()


@pytest.fixture(name="config")
def config_instance():
    return make_config()


@pytest.fixture(name="runner")
def runner_instance(config):
    return Runner(config)


@pytest.fixture(autouse=True, name="getter_refresh")
def noop_refreshable_getter():
    with patch(GETTER_REFRESH) as getter_refresh:
        yield getter_refresh


@pytest.fixture(autouse=True, name="config_refresh")
def disable_config_refresh():
    disabled = AsyncMock(side_effect=StopConfigRefresh("config refresh disabled"))
    with patch(CONFIG_REFRESH, new=disabled):
        yield disabled


@pytest.fixture(autouse=True, name="pipeline_manager")
def noop_pipeline_manager():
    with patch(PIPELINE_MANAGER, spec=PipelineManager) as pm:
        pm.return_value = pm  # same mock for instances
        yield pm


class TestRunner:

    async def test_external_stop_sets_stop_event(self, runner):
        assert not runner._stop_event.is_set()
        runner.stop()
        assert runner._stop_event.is_set()

    @pytest.mark.timeout(5)
    async def test_external_stop_shuts_down_cleanly(
        self, runner, pipeline_manager, config_refresh, getter_refresh
    ):
        pipeline_run_called = asyncio.Event()

        pipeline_manager.run.side_effect = mock_pipeline_run(pipeline_run_called.set)

        await asyncio.gather(
            runner.run(),
            stop_runner_after(runner, pipeline_run_called),
        )

        pipeline_manager.setup.assert_called()
        pipeline_manager.run.assert_called_once()
        config_refresh.assert_called()
        getter_refresh.assert_called()

    @pytest.mark.timeout(5)
    async def test_metrics_enabled_starts_exporter_and_injects_component_healthchecks(
        self,
        pipeline_manager,
    ):
        config = make_config(metrics_enabled=True)
        runner = Runner(config)
        component = NonCallableMagicMock()
        component.health = AsyncMock(return_value=True)
        pipeline_manager.components.return_value = [component]
        pipeline_manager.run.side_effect = mock_pipeline_run(None, regular_behavior=False)

        with patch(f"{MODULE}.PrometheusExporter", autospec=True) as exporter_cls:
            exporter = exporter_cls.return_value
            exporter_stopped = asyncio.Event()
            exporter.run.side_effect = exporter_stopped.wait
            exporter.stop.side_effect = exporter_stopped.set

            await runner.run()

        exporter_cls.assert_called_once_with(config.metrics)
        exporter.run.assert_awaited_once_with()
        exporter.wait_until_started.assert_awaited_once_with()
        exporter.update_healthchecks.assert_called_once_with([component.health])
        exporter.stop.assert_called_once_with()

    @pytest.mark.timeout(5)
    async def test_pipeline_manager_stops_by_itself(self, runner, pipeline_manager, config_refresh):
        pipeline_manager.run.side_effect = mock_pipeline_run(None, regular_behavior=False)
        config_refresh.side_effect = mock_config_refresh()

        await runner.run()

        assert runner._stop_event.is_set()
        pipeline_manager.run.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_pipeline_manager_exception_propagates(
        self, runner, pipeline_manager, config_refresh
    ):
        pipeline_manager.run.side_effect = RuntimeError("pipeline failed")
        config_refresh.side_effect = mock_config_refresh()

        exc = await run_until_exception(runner)

        assert isinstance(exc, RuntimeError)
        assert "pipeline failed" in str(exc)

    @pytest.mark.timeout(5)
    async def test_pipeline_setup_exception_propagates(
        self, runner, pipeline_manager, config_refresh
    ):
        pipeline_manager.setup.side_effect = RuntimeError("setup failed")
        config_refresh.side_effect = mock_config_refresh()

        exc = await run_until_exception(runner)

        assert isinstance(exc, RuntimeError)
        assert "setup failed" in str(exc)

    @pytest.mark.timeout(5)
    async def test_config_refresh_restarts_pipeline_with_new_config(
        self, runner, pipeline_manager, config_refresh
    ):
        new_config = make_config(version="v2")
        pipeline_restarted = asyncio.Event()

        config_refresh.side_effect = mock_config_refresh(new_config)

        pipeline_manager.run.side_effect = async_side_effects(
            mock_pipeline_run(),
            mock_pipeline_run(pipeline_restarted.set),
        )

        await asyncio.gather(runner.run(), stop_runner_after(runner, pipeline_restarted))

        assert pipeline_manager.run.call_count == 2
        assert pipeline_manager.setup.call_count == 2
        assert pipeline_manager.call_args_list[1].args[0] is new_config

    @pytest.mark.timeout(5)
    async def test_config_refresh_updates_config(self, runner, pipeline_manager, config_refresh):
        config = make_config(getter_refresh_interval=0.1)
        runner._config = config
        new_config = make_config(version="v2", getter_refresh_interval="illegal")

        pipeline_manager.run.side_effect = async_side_effects(
            mock_pipeline_run(),
            mock_pipeline_run(),
        )
        config_refresh.side_effect = mock_config_refresh(new_config)

        exc = await run_until_exception(runner)

        assert runner._config is new_config
        assert isinstance(exc, TypeError)

    @pytest.mark.timeout(5)
    async def test_config_refresh_exception_propagates(
        self, runner, pipeline_manager, config_refresh
    ):
        pipeline_manager.run.side_effect = mock_pipeline_run()
        config_refresh.side_effect = mock_config_refresh(RuntimeError("refresh failed"))

        exc = await run_until_exception(runner)

        assert isinstance(exc, RuntimeError)
        assert "refresh failed" in str(exc)

    @pytest.mark.timeout(5)
    async def test_refresh_disabled_runner_runs_until_stopped(self, runner, pipeline_manager):
        pipeline_running = asyncio.Event()

        pipeline_manager.run.side_effect = mock_pipeline_run(pipeline_running.set)

        result = await asyncio.gather(
            runner.run(), stop_runner_after(runner, pipeline_running), return_exceptions=True
        )

        assert result[0] is None
        pipeline_manager.run.assert_called_once()

    @pytest.mark.timeout(5)
    async def test_getter_exception_propagates(self, runner, pipeline_manager, config_refresh):
        class GetterError(RuntimeError):
            pass

        pipeline_manager.run.side_effect = mock_pipeline_run()
        config_refresh.side_effect = mock_config_refresh()

        with patch(GETTER_REFRESH, side_effect=GetterError("getter exploded")):
            exc = await run_until_exception(runner)

        assert isinstance(exc, GetterError)

    @pytest.mark.timeout(5)
    async def test_getter_loop_unexpected_stop_sets_stop_event(
        self, runner, pipeline_manager, config_refresh
    ):
        pipeline_manager.run.side_effect = mock_pipeline_run()
        config_refresh.side_effect = mock_config_refresh()

        async def getter_loop_returns_early(self_inner):
            return

        with patch.object(Runner, "_refresh_getters", getter_loop_returns_early):
            result = await asyncio.gather(runner.run(), return_exceptions=True)

        assert result[0] is None
        assert runner._stop_event.is_set()

    @pytest.mark.timeout(5)
    async def test_config_refresh_and_stop_race(self, runner, pipeline_manager, config_refresh):
        pipeline_manager.run.side_effect = async_side_effects(
            mock_pipeline_run(), mock_pipeline_run()
        )
        config_refresh.side_effect = mock_config_refresh(make_config(version="v2"))

        async def stop_concurrently():
            await asyncio.sleep(0)
            runner.stop()

        result = await asyncio.gather(runner.run(), stop_concurrently(), return_exceptions=True)

        assert result[0] is None

    @pytest.mark.timeout(5)
    async def test_pipeline_crash_and_concurrent_stop(
        self, runner, pipeline_manager, config_refresh
    ):
        class PipelineCrash(RuntimeError):
            pass

        pipeline_crashed = asyncio.Event()

        pipeline_manager.run.side_effect = mock_pipeline_run(
            pipeline_crashed.set, PipelineCrash("crash"), regular_behavior=False
        )
        config_refresh.side_effect = mock_config_refresh()

        async def stop_on_crash():
            await pipeline_crashed.wait()
            runner.stop()

        result = await asyncio.gather(runner.run(), stop_on_crash(), return_exceptions=True)

        assert isinstance(result[0], ExceptionGroup)
        assert any(isinstance(e, PipelineCrash) for e in result[0].exceptions)
        assert result[1] is None

    @pytest.mark.timeout(5)
    async def test_multiple_config_refreshes_each_restart_pipeline(
        self, runner, pipeline_manager, config_refresh
    ):
        v2 = make_config(version="v2")
        v3 = make_config(version="v3")
        pipeline_started_third_time = asyncio.Event()

        pipeline_manager.run.side_effect = async_side_effects(
            mock_pipeline_run(),
            mock_pipeline_run(),
            mock_pipeline_run(pipeline_started_third_time.set),
        )
        config_refresh.side_effect = mock_config_refresh(v2, v3)

        await asyncio.gather(runner.run(), stop_runner_after(runner, pipeline_started_third_time))

        assert pipeline_manager.run.call_count == 3
        versions = [call.args[0].version for call in pipeline_manager.call_args_list]
        assert versions == ["v1", "v2", "v3"]

    @pytest.mark.timeout(5)
    async def test_hard_shutdown_timeout_exceeded_pipeline_is_cancelled(
        self, runner, pipeline_manager, config_refresh
    ):
        pipeline_started = asyncio.Event()

        runner._config = make_config(hard_orchestrator_timeout=0.0)
        config_refresh.side_effect = mock_config_refresh()

        pipeline_manager.run.side_effect = mock_pipeline_run(
            pipeline_started.set, asyncio.Event(), regular_behavior=False
        )

        result = await asyncio.gather(
            runner.run(),
            stop_runner_after(runner, pipeline_started),
            return_exceptions=True,
        )

        assert result[0] is None
