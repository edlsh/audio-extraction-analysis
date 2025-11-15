"""Event consumption and batching for TUI."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable


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
        queue: asyncio.Queue[Any],
        on_batch: Callable[[list[Any]], None],
        config: EventConsumerConfig | None = None,
    ):
        """Initialize event consumer.

        Args:
            queue: Asyncio queue to consume events from
            on_batch: Callback function to handle batched events
            config: Consumer configuration (uses defaults if None)
        """
        self.queue = queue
        self.on_batch = on_batch
        self.config = config or EventConsumerConfig()
        self._running = False
        self._batch: list[Any] = []
        self._last_progress: dict[str, Any] = {}  # {stage: latest_progress_event}

    async def run(self) -> None:
        """Main event loop; call as background task.

        Continuously consumes events from the queue, batches them at the
        configured throttle interval, and calls on_batch with coalesced events.

        Runs until stop() is called.
        """
        self._running = True
        loop = asyncio.get_event_loop()

        while self._running:
            # Calculate deadline for this batch
            deadline = loop.time() + (self.config.throttle_ms / 1000)

            # Collect events until deadline
            while loop.time() < deadline and self._running:
                timeout = deadline - loop.time()
                if timeout <= 0:
                    break

                try:
                    event = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    self._add_to_batch(event)
                except asyncio.TimeoutError:
                    break  # Deadline reached

            # Flush batch
            if self._batch or self._last_progress:
                coalesced = self._coalesce_batch()
                if coalesced:
                    self.on_batch(coalesced)
                self._batch.clear()
                self._last_progress.clear()

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

    async def stop(self) -> None:
        """Stop consumer gracefully.

        Signals the consumer to stop after processing the current batch.
        Does not wait for the consumer task to finish.
        """
        self._running = False
