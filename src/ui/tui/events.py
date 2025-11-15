"""Event consumption and batching for TUI."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

_VALID_DROP_POLICIES = {"oldest", "newest"}
_STOP_SENTINEL = object()


class _DropAwareQueue(asyncio.Queue[Any]):
    """Async queue that enforces drop policy when full."""

    def __init__(self, *, maxsize: int, drop_policy: str) -> None:
        maxsize = max(1, maxsize)
        super().__init__(maxsize=maxsize)
        self._drop_policy = drop_policy

    def _evict_oldest(self) -> None:
        try:
            super().get_nowait()
        except asyncio.QueueEmpty:
            pass

    def put_nowait(self, item: Any) -> None:  # type: ignore[override]
        if self.maxsize > 0 and self.full():
            if item is _STOP_SENTINEL:
                self._evict_oldest()
            elif self._drop_policy == "oldest":
                self._evict_oldest()
            else:  # newest
                logger.debug("Dropping newest event due to full queue")
                return
        return super().put_nowait(item)

    async def put(self, item: Any) -> None:  # type: ignore[override]
        if self.maxsize > 0 and self.full():
            if item is _STOP_SENTINEL or self._drop_policy == "oldest":
                self._evict_oldest()
            else:
                logger.debug("Dropping newest event due to full queue")
                return
        await super().put(item)


@dataclass
class EventConsumerConfig:
    """Configuration for event batching and throttling.

    Attributes:
        throttle_ms: Batch interval in milliseconds (default: 50ms = 20 updates/sec)
        max_queue_size: Maximum queue size before backpressure (default: 1000)
        coalesce_progress: Merge multiple progress events per stage (default: True)
        drop_policy: Policy when queue full - "oldest" or "newest" (default: "oldest")
    """

    throttle_ms: int = 50
    max_queue_size: int = 1000
    coalesce_progress: bool = True
    drop_policy: str = "oldest"  # "oldest" | "newest"

    def __post_init__(self) -> None:
        if self.throttle_ms <= 0:
            raise ValueError("throttle_ms must be positive")
        if self.max_queue_size <= 0:
            raise ValueError("max_queue_size must be positive")
        normalized = self.drop_policy.lower()
        if normalized not in _VALID_DROP_POLICIES:
            raise ValueError(
                f"drop_policy must be one of {sorted(_VALID_DROP_POLICIES)}, got {self.drop_policy}"
            )
        self.drop_policy = normalized


class EventConsumer:
    """Consumes events from queue, batches, and calls reducer.

    Prevents UI thrashing by batching events at a fixed interval and
    coalescing rapid progress updates per stage.

    Usage:
        >>> consumer = EventConsumer(queue, on_batch, config)
        >>> task = asyncio.create_task(consumer.run())
        >>> # ... later ...
        >>> await consumer.stop()

    Example:
        >>> async def handle_batch(events):
        ...     for event in events:
        ...         state = apply_event(state, event)
        ...     update_ui(state)
        >>>
        >>> consumer = EventConsumer(event_queue, handle_batch)
        >>> await consumer.run()  # Runs until stopped
    """

    def __init__(
        self,
        queue: asyncio.Queue[Any] | None,
        on_batch: Callable[[list[Any]], None],
        config: EventConsumerConfig | None = None,
    ):
        """Initialize event consumer.

        Args:
            queue: Asyncio queue to consume events from (defaults to configured queue)
            on_batch: Callback function to handle batched events
            config: Consumer configuration (uses defaults if None)
        """
        self.config = config or EventConsumerConfig()
        self.queue = queue or self.create_queue(self.config)
        self.on_batch = on_batch
        self._running = False
        self._batch: list[Any] = []
        self._last_progress: dict[str, Any] = {}  # {stage: latest_progress_event}
        self._stopped: asyncio.Event | None = None

    @staticmethod
    def create_queue(config: EventConsumerConfig | None = None) -> asyncio.Queue[Any]:
        """Create a queue that honors the supplied configuration."""

        cfg = config or EventConsumerConfig()
        return _DropAwareQueue(maxsize=cfg.max_queue_size, drop_policy=cfg.drop_policy)

    async def run(self) -> None:
        """Main event loop; call as background task.

        Continuously consumes events from the queue, batches them at the
        configured throttle interval, and calls on_batch with coalesced events.

        Runs until stop() is called.
        """
        if self._running:
            raise RuntimeError("EventConsumer is already running")

        self._running = True
        self._stopped = asyncio.Event()
        loop = asyncio.get_running_loop()

        try:
            while self._running:
                deadline = loop.time() + (self.config.throttle_ms / 1000)
                sentinel_received = False

                while loop.time() < deadline:
                    timeout = max(deadline - loop.time(), 0)
                    if timeout <= 0:
                        break

                    try:
                        event = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        break

                    if event is _STOP_SENTINEL:
                        sentinel_received = True
                        self._running = False
                        break

                    self._add_to_batch(event)

                self._flush_batch()

                if sentinel_received:
                    break
        finally:
            self._batch.clear()
            self._last_progress.clear()
            if self._stopped:
                self._stopped.set()
            self._running = False

    def _add_to_batch(self, event: Any) -> None:
        """Add event to batch with coalescing logic.

        Args:
            event: Event to add
        """
        if self.config.coalesce_progress and event.type == "stage_progress":
            # Keep only latest progress per stage
            if event.stage:
                self._last_progress[event.stage] = event
        else:
            self._batch.append(event)

    def _coalesce_batch(self) -> list[Any]:
        """Merge coalesced progress events into batch.

        Returns:
            List of all events (batch + coalesced progress)
        """
        # Combine batch with latest progress events
        return [*self._batch, *self._last_progress.values()]

    def _flush_batch(self) -> None:
        """Flush current batch to callback if there are pending events."""
        if not (self._batch or self._last_progress):
            return

        coalesced = self._coalesce_batch()
        if not coalesced:
            self._batch.clear()
            self._last_progress.clear()
            return

        try:
            self.on_batch(coalesced)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error processing event batch: %s", exc, exc_info=True)
        finally:
            self._batch.clear()
            self._last_progress.clear()

    async def stop(self) -> None:
        """Stop consumer gracefully.

        Signals the consumer to stop after processing the current batch
        and waits for the run loop to exit.
        """
        if not self._running:
            return

        if self._stopped is None:
            self._stopped = asyncio.Event()

        # Wake the consumer by enqueueing sentinel
        try:
            self.queue.put_nowait(_STOP_SENTINEL)
        except asyncio.QueueFull:
            # Force room for sentinel by evicting oldest event
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.queue.put_nowait(_STOP_SENTINEL)

        await self._stopped.wait()
