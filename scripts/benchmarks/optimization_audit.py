#!/usr/bin/env python3
"""Micro-benchmark suite for Phase 1/2 optimization audit.

This script measures the performance impact of recent optimization changes:
1) URL-style pipeline latency with vs without `skip_extraction`
2) Provider scan overhead (`get_configured_providers`) cold vs cached
3) FFprobe cache hit/miss behavior and latency
4) Provider speed metadata lookup without provider instantiation

Usage:
    python scripts/benchmarks/optimization_audit.py
    python scripts/benchmarks/optimization_audit.py --iterations 8 --json-output reports/opt-audit.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import tempfile
import wave
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from types import TracebackType
from typing import Any
from unittest.mock import patch

from loguru import logger as loguru_logger

# Default to warning-level logs so benchmark output remains readable.
loguru_logger.remove()
loguru_logger.add(sys.stderr, level="WARNING")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.loguru_config import configure_loguru

configure_loguru(level="WARNING", json_file=False, debug_file=False)

from src.models.transcription import TranscriptionResult
from src.pipeline import simple_pipeline as simple_pipeline_module
from src.pipeline.simple_pipeline import AudioQuality
from src.providers import provider_utils
from src.providers.base import ProviderMeta
from src.providers.factory import TranscriptionProviderFactory
from src.services.ffmpeg_core import (
    check_ffmpeg_available,
    clear_probe_cache,
    get_probe_cache_stats,
    probe_media_sync,
)
from src.services.transcription import TranscriptionService


@dataclass(frozen=True)
class TimingSummary:
    """Summary statistics for a sample of elapsed durations."""

    iterations: int
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float

    @classmethod
    def from_samples(cls, samples_seconds: list[float]) -> TimingSummary:
        """Build summary from raw second-based samples."""
        if not samples_seconds:
            raise ValueError("Cannot summarize empty sample set")

        sorted_samples = sorted(samples_seconds)
        p95_index = max(0, math.ceil(len(sorted_samples) * 0.95) - 1)

        return cls(
            iterations=len(samples_seconds),
            mean_ms=mean(samples_seconds) * 1000.0,
            median_ms=median(samples_seconds) * 1000.0,
            min_ms=sorted_samples[0] * 1000.0,
            max_ms=sorted_samples[-1] * 1000.0,
            p95_ms=sorted_samples[p95_index] * 1000.0,
        )


class _NoopProgress:
    """Minimal progress context used by the benchmark pipeline path."""

    def __enter__(self) -> _NoopProgress:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = (exc_type, exc, traceback)
        return None

    def update(
        self,
        completed: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        _ = (completed, total, message)
        return None


class _NoopConsole:
    """Minimal console manager compatible with pipeline expectations."""

    def setup_logging(self, logger_obj: Any) -> None:
        _ = logger_obj
        return None

    def print_stage(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)
        return None

    def progress_context(self, *args: Any, **kwargs: Any) -> _NoopProgress:
        _ = (args, kwargs)
        return _NoopProgress()

    def print_summary(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)
        return None


class _BenchmarkTranscriptionService:
    """Lightweight transcription service stub for extraction-focused benchmarking."""

    def __init__(self, cache: Any | None = None) -> None:
        _ = cache

    def save_transcription_result(
        self,
        result: TranscriptionResult,
        output_path: Path,
        provider_name: str | None = None,
    ) -> None:
        _ = provider_name
        output_path.write_text(result.transcript, encoding="utf-8")


async def _fake_transcribe_audio(
    audio_path: Path,
    provider: str,
    language: str,
    cm: _NoopConsole,
    service: _BenchmarkTranscriptionService,
    reporter: Any,
) -> tuple[TranscriptionResult, float]:
    """Synthetic transcription stage used to isolate extraction latency."""
    _ = (provider, language, cm, service, reporter)

    transcript = TranscriptionResult(
        transcript="benchmark transcript",
        duration=1.0,
        generated_at=datetime.now(UTC),
        audio_file=str(audio_path),
        provider_name="benchmark",
    )
    return transcript, 0.0


async def _fake_analyze_transcript(
    transcript: TranscriptionResult,
    output_dir: Path,
    input_stem: str,
    analysis_style: str,
    cm: _NoopConsole,
    reporter: Any,
) -> tuple[list[str], float]:
    """Synthetic analysis stage used to isolate extraction latency."""
    _ = (transcript, analysis_style, cm, reporter)

    analysis_path = output_dir / f"{input_stem}_benchmark.md"
    analysis_path.write_text("# benchmark\n", encoding="utf-8")
    return [str(analysis_path)], 0.0


@dataclass
class _FactorySpy:
    """Factory stand-in to verify metadata lookup path avoids instantiation."""

    fixed_speed: float = 2.75
    get_meta_calls: int = 0
    create_provider_calls: int = 0

    def get_provider_meta(
        self,
        provider_name: str,
        include_test_providers: bool | None = None,
    ) -> ProviderMeta | None:
        _ = include_test_providers
        self.get_meta_calls += 1
        return ProviderMeta(
            name="Benchmark Provider",
            provider_key=provider_name,
            estimated_speed_mb_per_sec=self.fixed_speed,
        )

    def create_provider(self, *args: Any, **kwargs: Any) -> Any:
        _ = (args, kwargs)
        self.create_provider_calls += 1
        raise RuntimeError("create_provider should not be called for speed metadata lookup")


def _create_dummy_wav(path: Path, duration_seconds: float = 1.0, sample_rate: int = 16_000) -> None:
    """Create a tiny valid mono WAV file for local benchmarking."""
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    """Return ratio when denominator is non-zero."""
    if denominator <= 0:
        return None
    return numerator / denominator


def configure_logging(verbose_logs: bool) -> None:
    """Configure benchmark logging verbosity."""
    loguru_logger.remove()
    level = "DEBUG" if verbose_logs else "WARNING"
    loguru_logger.add(sys.stderr, level=level)


async def _run_pipeline_case(
    input_audio_path: Path,
    output_dir: Path,
    *,
    skip_extraction: bool,
) -> tuple[float, str]:
    """Execute one pipeline run and return elapsed seconds + extraction status."""
    start = perf_counter()
    result = await simple_pipeline_module.process_pipeline_v2(
        input_path=input_audio_path,
        output_dir=output_dir,
        quality=AudioQuality.STANDARD,
        language="en",
        provider="auto",
        analysis_style="concise",
        console_manager=_NoopConsole(),
        skip_extraction=skip_extraction,
    )
    elapsed_seconds = perf_counter() - start

    if not result.success:
        raise RuntimeError(f"Pipeline benchmark failed: {result.error_messages}")

    extraction_result = result.stage_results.get("extraction")
    extraction_status = extraction_result.status if extraction_result is not None else "unknown"
    return elapsed_seconds, extraction_status


async def benchmark_url_flow_latency(
    input_audio_path: Path,
    *,
    iterations: int,
    warmup: int,
) -> dict[str, Any]:
    """Benchmark URL-style pipeline flow with and without extraction bypass."""
    try:
        check_ffmpeg_available(timeout=5.0)
    except Exception as exc:
        return {
            "skipped": True,
            "reason": f"FFmpeg unavailable: {exc}",
        }

    with tempfile.TemporaryDirectory(prefix="bench_url_flow_") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)

        with (
            patch.object(
                simple_pipeline_module,
                "TranscriptionService",
                _BenchmarkTranscriptionService,
            ),
            patch.object(
                simple_pipeline_module,
                "_transcribe_audio",
                _fake_transcribe_audio,
            ),
            patch.object(
                simple_pipeline_module,
                "_analyze_transcript",
                _fake_analyze_transcript,
            ),
        ):
            for index in range(warmup):
                await _run_pipeline_case(
                    input_audio_path,
                    temp_dir / f"warmup_without_skip_{index}",
                    skip_extraction=False,
                )
                await _run_pipeline_case(
                    input_audio_path,
                    temp_dir / f"warmup_with_skip_{index}",
                    skip_extraction=True,
                )

            without_skip_samples: list[float] = []
            with_skip_samples: list[float] = []
            without_skip_statuses: list[str] = []
            with_skip_statuses: list[str] = []

            for index in range(iterations):
                without_elapsed, without_status = await _run_pipeline_case(
                    input_audio_path,
                    temp_dir / f"without_skip_{index}",
                    skip_extraction=False,
                )
                with_elapsed, with_status = await _run_pipeline_case(
                    input_audio_path,
                    temp_dir / f"with_skip_{index}",
                    skip_extraction=True,
                )

                without_skip_samples.append(without_elapsed)
                with_skip_samples.append(with_elapsed)
                without_skip_statuses.append(without_status)
                with_skip_statuses.append(with_status)

    without_summary = TimingSummary.from_samples(without_skip_samples)
    with_summary = TimingSummary.from_samples(with_skip_samples)

    return {
        "skipped": False,
        "iterations": iterations,
        "warmup": warmup,
        "without_skip_extraction": asdict(without_summary),
        "with_skip_extraction": asdict(with_summary),
        "speedup_factor": _safe_ratio(without_summary.mean_ms, with_summary.mean_ms),
        "observed_extraction_stage_statuses": {
            "without_skip_extraction": sorted(set(without_skip_statuses)),
            "with_skip_extraction": sorted(set(with_skip_statuses)),
        },
    }


def _clear_provider_discovery_caches() -> None:
    """Reset provider discovery caches for cold-start measurement."""
    TranscriptionProviderFactory._clear_configured_providers_cache()
    with provider_utils._sdk_cache_lock:
        provider_utils._sdk_availability_cache.clear()
        provider_utils._sdk_warning_emitted.clear()


def benchmark_provider_scan_overhead(*, cached_iterations: int) -> dict[str, Any]:
    """Benchmark provider configuration scan cold call vs cached calls."""
    _clear_provider_discovery_caches()

    cold_start = perf_counter()
    configured = TranscriptionProviderFactory.get_configured_providers()
    cold_elapsed_ms = (perf_counter() - cold_start) * 1000.0

    cached_samples: list[float] = []
    for _ in range(cached_iterations):
        start = perf_counter()
        TranscriptionProviderFactory.get_configured_providers()
        cached_samples.append(perf_counter() - start)

    cached_summary = TimingSummary.from_samples(cached_samples)

    return {
        "configured_providers": configured,
        "configured_count": len(configured),
        "cold_call_ms": cold_elapsed_ms,
        "cached_calls": asdict(cached_summary),
        "speedup_factor": _safe_ratio(cold_elapsed_ms, cached_summary.mean_ms),
    }


def benchmark_probe_cache_effectiveness(
    audio_path: Path,
    *,
    cached_iterations: int,
) -> dict[str, Any]:
    """Measure FFprobe cache miss/hit latency and cache metrics."""
    clear_probe_cache()
    stats_before = get_probe_cache_stats()

    miss_start = perf_counter()
    miss_result = probe_media_sync(audio_path)
    miss_elapsed_ms = (perf_counter() - miss_start) * 1000.0
    stats_after_miss = get_probe_cache_stats()

    hit_samples: list[float] = []
    for _ in range(cached_iterations):
        hit_start = perf_counter()
        probe_media_sync(audio_path)
        hit_samples.append(perf_counter() - hit_start)

    hit_summary = TimingSummary.from_samples(hit_samples)
    stats_after_hits = get_probe_cache_stats()

    return {
        "probe_duration_seconds": miss_result.duration,
        "probe_size_mb": miss_result.size_mb,
        "first_miss_ms": miss_elapsed_ms,
        "cached_hits": asdict(hit_summary),
        "speedup_factor": _safe_ratio(miss_elapsed_ms, hit_summary.mean_ms),
        "cache_stats": {
            "before": stats_before,
            "after_first_miss": stats_after_miss,
            "after_cached_hits": stats_after_hits,
        },
    }


def benchmark_metadata_lookup(*, iterations: int) -> dict[str, Any]:
    """Verify provider speed lookup path does not instantiate providers."""
    service = TranscriptionService()
    original_factory = service.factory
    spy_factory = _FactorySpy()
    service.factory = spy_factory  # type: ignore[assignment]

    try:
        start = perf_counter()
        last_speed = 0.0
        for _ in range(iterations):
            last_speed = service._get_provider_speed_by_name("benchmark")
        elapsed_ms = (perf_counter() - start) * 1000.0
    finally:
        service.factory = original_factory

    return {
        "iterations": iterations,
        "reported_speed_mb_per_sec": last_speed,
        "expected_speed_mb_per_sec": spy_factory.fixed_speed,
        "total_ms": elapsed_ms,
        "avg_us_per_lookup": (elapsed_ms * 1000.0) / iterations,
        "factory_get_provider_meta_calls": spy_factory.get_meta_calls,
        "factory_create_provider_calls": spy_factory.create_provider_calls,
        "instantiation_avoided": spy_factory.create_provider_calls == 0,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    """Run the full benchmark suite and return a structured report."""
    with tempfile.TemporaryDirectory(prefix="optimization_audit_") as temp_root_raw:
        temp_root = Path(temp_root_raw)
        input_audio_path = temp_root / "benchmark_input.wav"
        _create_dummy_wav(input_audio_path, duration_seconds=float(args.audio_duration_seconds))

        url_flow = asyncio.run(
            benchmark_url_flow_latency(
                input_audio_path,
                iterations=int(args.iterations),
                warmup=int(args.warmup),
            )
        )

        provider_scan = benchmark_provider_scan_overhead(
            cached_iterations=int(args.provider_cached_iterations)
        )

        probe_cache = benchmark_probe_cache_effectiveness(
            input_audio_path,
            cached_iterations=int(args.probe_cached_iterations),
        )

        metadata_lookup = benchmark_metadata_lookup(
            iterations=int(args.metadata_iterations),
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "iterations": int(args.iterations),
            "warmup": int(args.warmup),
            "audio_duration_seconds": float(args.audio_duration_seconds),
            "provider_cached_iterations": int(args.provider_cached_iterations),
            "probe_cached_iterations": int(args.probe_cached_iterations),
            "metadata_iterations": int(args.metadata_iterations),
        },
        "results": {
            "url_flow_latency": url_flow,
            "provider_scan_overhead": provider_scan,
            "probe_cache_effectiveness": probe_cache,
            "metadata_lookup": metadata_lookup,
        },
    }


def _fmt_ms(value: float | None) -> str:
    """Format millisecond values for console output."""
    if value is None:
        return "n/a"
    return f"{value:.3f} ms"


def _fmt_ratio(value: float | None) -> str:
    """Format speedup ratio values."""
    if value is None:
        return "n/a"
    return f"{value:.2f}x"


def print_report(report: dict[str, Any]) -> None:
    """Pretty-print benchmark report to stdout."""
    results = report["results"]
    url_flow = results["url_flow_latency"]
    provider_scan = results["provider_scan_overhead"]
    probe_cache = results["probe_cache_effectiveness"]
    metadata_lookup = results["metadata_lookup"]

    print("\n=== Optimization Audit Micro-Benchmark ===")
    print(f"Generated at: {report['generated_at']}")

    print("\n1) URL flow latency (skip_extraction)")
    if url_flow.get("skipped"):
        print(f"   Skipped: {url_flow.get('reason', 'unknown reason')}")
    else:
        without_skip = url_flow["without_skip_extraction"]
        with_skip = url_flow["with_skip_extraction"]
        print(f"   without skip_extraction mean: {_fmt_ms(without_skip['mean_ms'])}")
        print(f"   with skip_extraction mean:    {_fmt_ms(with_skip['mean_ms'])}")
        print(f"   speedup: {_fmt_ratio(url_flow.get('speedup_factor'))}")
        print(
            "   extraction statuses:",
            url_flow.get("observed_extraction_stage_statuses", {}),
        )

    print("\n2) Provider scan overhead")
    print(f"   configured providers: {provider_scan['configured_providers']}")
    print(f"   cold call: {_fmt_ms(provider_scan['cold_call_ms'])}")
    print(f"   cached mean: {_fmt_ms(provider_scan['cached_calls']['mean_ms'])}")
    print(f"   speedup: {_fmt_ratio(provider_scan.get('speedup_factor'))}")

    print("\n3) Probe cache effectiveness")
    print(f"   first miss: {_fmt_ms(probe_cache['first_miss_ms'])}")
    print(f"   cached hit mean: {_fmt_ms(probe_cache['cached_hits']['mean_ms'])}")
    print(f"   speedup: {_fmt_ratio(probe_cache.get('speedup_factor'))}")
    print(f"   cache stats: {probe_cache['cache_stats']['after_cached_hits']}")

    print("\n4) Metadata lookup (no instantiation)")
    print(f"   avg lookup: {metadata_lookup['avg_us_per_lookup']:.3f} us")
    print(f"   get_provider_meta calls: {metadata_lookup['factory_get_provider_meta_calls']}")
    print(f"   create_provider calls:   {metadata_lookup['factory_create_provider_calls']}")
    print(f"   instantiation avoided:   {metadata_lookup['instantiation_avoided']}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for benchmark controls."""
    parser = argparse.ArgumentParser(description="Run optimization audit micro-benchmarks")
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Measured iterations for URL flow benchmark per mode.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup iterations for URL flow benchmark per mode.",
    )
    parser.add_argument(
        "--audio-duration-seconds",
        type=float,
        default=1.0,
        help="Duration of generated dummy WAV input file.",
    )
    parser.add_argument(
        "--provider-cached-iterations",
        type=int,
        default=30,
        help="Number of cached calls for provider scan benchmark.",
    )
    parser.add_argument(
        "--probe-cached-iterations",
        type=int,
        default=30,
        help="Number of cached probes for probe-cache benchmark.",
    )
    parser.add_argument(
        "--metadata-iterations",
        type=int,
        default=50_000,
        help="Number of provider speed lookups for metadata benchmark.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional file path to write the full JSON report.",
    )
    parser.add_argument(
        "--verbose-logs",
        action="store_true",
        help="Show INFO/DEBUG logs from underlying services.",
    )

    args = parser.parse_args()

    if args.iterations < 1:
        raise ValueError("--iterations must be >= 1")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")
    if args.audio_duration_seconds <= 0:
        raise ValueError("--audio-duration-seconds must be > 0")
    if args.provider_cached_iterations < 1:
        raise ValueError("--provider-cached-iterations must be >= 1")
    if args.probe_cached_iterations < 1:
        raise ValueError("--probe-cached-iterations must be >= 1")
    if args.metadata_iterations < 1:
        raise ValueError("--metadata-iterations must be >= 1")

    return args


def main() -> int:
    """CLI entrypoint for the optimization benchmark audit."""
    try:
        args = parse_args()
        configure_logging(verbose_logs=bool(args.verbose_logs))
        report = build_report(args)
        print_report(report)

        if args.json_output is not None:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"\nJSON report written to: {args.json_output}")

        return 0
    except Exception as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
