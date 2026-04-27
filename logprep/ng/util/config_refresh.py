"""
Runner module
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from logprep.ng.util.configuration import Configuration

logger = logging.getLogger("config_refresh")


async def config_refresh_gen(
    initial_config: Configuration,
    stop_event: asyncio.Event,
    *,
    yield_initial: bool = True,
) -> AsyncGenerator[Configuration, None]:
    """
    Produce a `Configuration` every time a new configuration version has been detected.
    The generator runs endlessly, if not stopped through the `stop_event` or a disabled
    configuration refresh (`refresh_interval` set to `None`).

    Parameters
    ----------
    initial_config : Configuration
        The starting configuration
    stop_event : asyncio.Event
        Event to signal that the generator shall stop
    yield_initial : bool, optional
        Whether to also yield the initial configuration once; defaults to `True`

    Returns
    -------
    AsyncGenerator[Configuration, None]
        A `Configuration` every time a new configuration version has been detected

    Yields
    ------
    Iterator[Configuration]
        A `Configuration` every time a new configuration version has been detected
    """
    config = initial_config

    current_config_version = config.version
    refresh_interval = config.config_refresh_interval

    if refresh_interval is None:
        logger.debug("Config refresh has been disabled.")
        return

    loop = asyncio.get_running_loop()
    next_run = loop.time() + refresh_interval

    if yield_initial:
        yield config

    while not stop_event.is_set():
        sleep_time = next_run - loop.time()
        if sleep_time < 0:
            sleep_time = 0.0

        try:
            # trick to wait for any of both, stop_event or sleep timeout
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_time)
            logger.debug("Config refresh sleep stopped prematurely due to stop_event. Exiting...")
            assert stop_event.is_set()
            break
        except TimeoutError:
            # stop_event has not been set, continue with normal loop
            logger.debug("Config refresh slept whole timeout. Continuing...")
            pass
        except asyncio.CancelledError:
            logger.debug("Config refresh cancelled. Exiting...")
            raise

        try:
            # TODO return a fresh config instead of in-place updates
            await config.reload()
        except asyncio.CancelledError:
            logger.debug("Config reload cancelled. Exiting...")
            raise
        except Exception:
            logger.exception("scheduled config reload failed")
            raise
        if config.version != current_config_version:
            logger.info("Detected new config version: %s", config.version)
            current_config_version = config.version
            yield config

        refresh_interval = config.config_refresh_interval
        if refresh_interval is None:
            logger.debug("Config refresh has been disabled.")
            break

        next_run += refresh_interval
