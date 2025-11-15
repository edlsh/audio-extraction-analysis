"""Tests for TUI event consumer with batching and throttling."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from src.models.events import Event
from src.ui.tui.events import EventConsumer, EventConsumerConfig


class TestEventConsumerConfig:
    """Tests for EventConsumerConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EventConsumerConfig()

        assert config.throttle_ms == 50
        assert config.max_queue_size == 1000
        assert config.coalesce_progress is True
        assert config.drop_policy == "oldest"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = EventConsumerConfig(
            throttle_ms=100,
            max_queue_size=500,
            coalesce_progress=False,
            drop_policy="newest",
        )

        assert config.throttle_ms == 100
        assert config.max_queue_size == 500
        assert config.coalesce_progress is False
        assert config.drop_policy == "newest"


class TestEventConsumerBatching:
    """Tests for event batching behavior."""

    @pytest.mark.asyncio
    async def test_batches_events_at_throttle_interval(self):
        """Test that events are batched at the configured throttle interval."""
        queue = asyncio.Queue()
        batches = []

        def on_batch(events):
            batches.append(events.copy())

        config = EventConsumerConfig(throttle_ms=100)
        consumer = EventConsumer(queue, on_batch, config)

        # Start consumer
        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit 10 events rapidly (every 10ms)
            for i in range(10):
                await queue.put(Event(type="log", data={"message": f"Event {i}", "level": "INFO"}))
                await asyncio.sleep(0.01)

            # Wait for batch processing
            await asyncio.sleep(0.15)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)  # Let consumer finish
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        # Should have 1-2 batches (100ms throttle with 100ms of events)
        assert 1 <= len(batches) <= 2
        total_events = sum(len(batch) for batch in batches)
        assert total_events == 10

    @pytest.mark.asyncio
    async def test_empty_queue_produces_no_batch(self):
        """Test that no batch is produced when queue is empty."""
        queue = asyncio.Queue()
        batches = []

        consumer = EventConsumer(
            queue, lambda e: batches.append(e), EventConsumerConfig(throttle_ms=50)
        )

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Wait for a couple throttle intervals with no events
            await asyncio.sleep(0.15)
        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        # Should have no batches since queue was empty
        assert len(batches) == 0


class TestEventConsumerCoalescing:
    """Tests for progress event coalescing."""

    @pytest.mark.asyncio
    async def test_coalesces_progress_events(self):
        """Test that multiple progress events for same stage are coalesced."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=50, coalesce_progress=True)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit 100 progress events for same stage rapidly
            for i in range(100):
                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="extract",
                        data={"completed": i, "total": 100},
                    )
                )

            # Wait for batch
            await asyncio.sleep(0.1)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        # Should have coalesced to very few progress events
        all_events = [e for batch in batches for e in batch]
        progress_events = [e for e in all_events if e.type == "stage_progress"]

        # Should be coalesced to 1-2 events (one per batch)
        assert len(progress_events) <= 2

        # Latest progress should be preserved
        if progress_events:
            latest = progress_events[-1]
            assert latest.data["completed"] >= 98  # Near end

    @pytest.mark.asyncio
    async def test_coalesces_per_stage(self):
        """Test that coalescing is done per-stage (multiple stages tracked)."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=100, coalesce_progress=True)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit progress for two different stages
            for i in range(50):
                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="extract",
                        data={"completed": i, "total": 100},
                    )
                )
                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="transcribe",
                        data={"completed": i, "total": 100},
                    )
                )

            await asyncio.sleep(0.15)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        all_events = [e for batch in batches for e in batch]

        extract_progress = [
            e for e in all_events if e.type == "stage_progress" and e.stage == "extract"
        ]
        transcribe_progress = [
            e for e in all_events if e.type == "stage_progress" and e.stage == "transcribe"
        ]

        # Each stage should have 1-2 coalesced progress events
        assert len(extract_progress) <= 2
        assert len(transcribe_progress) <= 2

    @pytest.mark.asyncio
    async def test_non_progress_events_not_coalesced(self):
        """Test that non-progress events are never coalesced."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=50, coalesce_progress=True)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit 10 non-progress events
            for i in range(10):
                await queue.put(Event(type="log", data={"message": f"Log {i}", "level": "INFO"}))

            await asyncio.sleep(0.1)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        all_events = [e for batch in batches for e in batch]
        log_events = [e for e in all_events if e.type == "log"]

        # All log events should be preserved
        assert len(log_events) == 10

    @pytest.mark.asyncio
    async def test_coalescing_disabled(self):
        """Test that coalescing can be disabled."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=50, coalesce_progress=False)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit 20 progress events
            for i in range(20):
                await queue.put(
                    Event(
                        type="stage_progress",
                        stage="extract",
                        data={"completed": i, "total": 100},
                    )
                )

            await asyncio.sleep(0.1)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        all_events = [e for batch in batches for e in batch]

        # All progress events should be preserved when coalescing disabled
        assert len(all_events) == 20


class TestEventConsumerLifecycle:
    """Tests for consumer lifecycle (start/stop)."""

    @pytest.mark.asyncio
    async def test_consumer_starts_and_stops_gracefully(self):
        """Test consumer can be started and stopped."""
        queue = asyncio.Queue()
        batches = []

        consumer = EventConsumer(
            queue, lambda e: batches.append(e), EventConsumerConfig(throttle_ms=50)
        )

        task = asyncio.create_task(consumer.run())

        # Give consumer time to start
        await asyncio.sleep(0.01)

        # Consumer should be running
        assert consumer._running is True

        # Stop consumer
        await consumer.stop()

        # Give time for consumer to finish current batch
        await asyncio.sleep(0.15)

        # Consumer should have stopped
        assert consumer._running is False

        # Clean up task
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_multiple_start_stop_cycles(self):
        """Test consumer can be started and stopped multiple times."""
        queue = asyncio.Queue()
        batches = []

        for _ in range(3):
            consumer = EventConsumer(
                queue, lambda e: batches.append(e), EventConsumerConfig(throttle_ms=30)
            )

            task = asyncio.create_task(consumer.run())
            await asyncio.sleep(0.05)
            await consumer.stop()
            await asyncio.sleep(0.05)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_stop_flushes_pending_events(self):
        """Stop should flush any pending events immediately."""
        queue = asyncio.Queue()
        batches: list[list[Event]] = []

        consumer = EventConsumer(
            queue,
            lambda e: batches.append(e.copy()),
            EventConsumerConfig(throttle_ms=500),
        )

        task = asyncio.create_task(consumer.run())

        try:
            await queue.put(Event(type="log", data={"message": "pending"}))
            await asyncio.sleep(0.05)

            await consumer.stop()
            await task
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        assert batches and batches[0][0].data["message"] == "pending"

    @pytest.mark.asyncio
    async def test_stop_returns_when_queue_idle(self):
        """Stop returns even if consumer is waiting on empty queue."""
        queue = asyncio.Queue()
        consumer = EventConsumer(queue, lambda e: None)
        task = asyncio.create_task(consumer.run())

        try:
            await asyncio.sleep(0.01)
            await asyncio.wait_for(consumer.stop(), timeout=0.5)
            await task
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


class TestEventConsumerMixedEvents:
    """Tests for handling mixed event types."""

    @pytest.mark.asyncio
    async def test_mixed_events_batch_correctly(self):
        """Test that batches correctly mix progress and non-progress events."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=100, coalesce_progress=True)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit mixed events
            events_sent = []
            for i in range(20):
                # Progress event
                prog = Event(
                    type="stage_progress",
                    stage="extract",
                    data={"completed": i, "total": 100},
                )
                await queue.put(prog)
                events_sent.append("progress")

                # Non-progress event
                if i % 3 == 0:
                    log = Event(type="log", data={"message": f"Log {i}", "level": "INFO"})
                    await queue.put(log)
                    events_sent.append("log")

            await asyncio.sleep(0.15)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        all_events = [e for batch in batches for e in batch]

        # Should have coalesced progress but kept all logs
        progress_count = len([e for e in all_events if e.type == "stage_progress"])
        log_count = len([e for e in all_events if e.type == "log"])

        assert progress_count <= 2  # Coalesced
        assert log_count == 7  # All preserved (every 3rd iteration of 0-19)

    @pytest.mark.asyncio
    async def test_batch_ordering_preserved_within_type(self):
        """Test that event ordering is preserved within event types."""
        queue = asyncio.Queue()
        batches = []

        config = EventConsumerConfig(throttle_ms=100, coalesce_progress=False)
        consumer = EventConsumer(queue, lambda e: batches.append(e), config)

        consumer_task = asyncio.create_task(consumer.run())

        try:
            # Emit ordered log events
            for i in range(10):
                await queue.put(Event(type="log", data={"message": f"Log {i}", "level": "INFO"}))

            await asyncio.sleep(0.15)

        finally:
            await consumer.stop()
            await asyncio.sleep(0.05)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

        all_events = [e for batch in batches for e in batch]

        # Check ordering
        for i, event in enumerate(all_events):
            assert event.data["message"] == f"Log {i}"


class TestEventConsumerQueuePolicies:
    """Tests for queue sizing and drop policies."""

    def test_create_queue_respects_max_size(self):
        """Queue factory should size queue according to config."""
        config = EventConsumerConfig(max_queue_size=128)
        queue = EventConsumer.create_queue(config)
        assert queue.maxsize == 128

    def test_oldest_drop_policy_evicts_oldest(self):
        """Oldest policy evicts earliest event when full."""
        config = EventConsumerConfig(max_queue_size=2, drop_policy="oldest")
        queue = EventConsumer.create_queue(config)

        e1 = Event(type="log", data={"idx": 1})
        e2 = Event(type="log", data={"idx": 2})
        e3 = Event(type="log", data={"idx": 3})

        queue.put_nowait(e1)
        queue.put_nowait(e2)
        queue.put_nowait(e3)

        first = queue.get_nowait()
        second = queue.get_nowait()
        assert first is e2
        assert second is e3

    def test_newest_drop_policy_discards_new_event(self):
        """Newest policy discards incoming event when queue is full."""
        config = EventConsumerConfig(max_queue_size=2, drop_policy="newest")
        queue = EventConsumer.create_queue(config)

        e1 = Event(type="log", data={"idx": 1})
        e2 = Event(type="log", data={"idx": 2})
        e3 = Event(type="log", data={"idx": 3})

        queue.put_nowait(e1)
        queue.put_nowait(e2)
        queue.put_nowait(e3)

        first = queue.get_nowait()
        second = queue.get_nowait()
        assert first is e1
        assert second is e2
