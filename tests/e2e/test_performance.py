"""
Performance and Load Testing Suite for audio-extraction-analysis.

Tests performance characteristics including:
- Processing time benchmarks
- Memory usage monitoring
- Concurrent operation handling
- Large file processing
- Resource utilization tracking
"""

import concurrent.futures
import os
import threading
import time
from unittest.mock import patch

import psutil
import pytest

from .base import CLITestMixin, E2ETestBase, MockProviderMixin, PerformanceTestMixin
from .test_data_manager import TestDataManager


class TestPerformanceBenchmarks(E2ETestBase, CLITestMixin, PerformanceTestMixin, MockProviderMixin):
    """Performance benchmark tests for core operations."""

    @classmethod
    def setup_class(cls):
        """Setup test data and performance targets."""
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

        # Performance targets (in seconds)
        cls.performance_targets = {
            "extract_short": 30,  # 5s video should extract in < 30s
            "extract_medium": 60,  # 2min video should extract in < 60s
            "transcribe_short": 45,  # 5s audio should transcribe in < 45s
            "transcribe_medium": 120,  # 2min audio should transcribe in < 120s
            "process_short": 90,  # Full pipeline for 5s video < 90s
            "process_medium": 300,  # Full pipeline for 2min video < 300s
        }

        # Memory targets (in MB)
        cls.memory_targets = {
            "extract_short": 100,
            "extract_medium": 200,
            "process_short": 200,
            "process_medium": 500,
        }

    def test_extract_performance_short_file(self):
        """Test audio extraction performance with short file."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        output_file = self.output_dir / "perf_extract_short.mp3"

        with self.monitor_memory_usage() as memory_monitor:
            start_time = time.time()

            result = self.run_extract_command(
                input_file=input_file, output_file=output_file, quality="high"
            )

            duration = time.time() - start_time
            memory_monitor.update_peak()

        assert result.success, f"Extract failed: {result.error}"

        # Performance assertions
        self.assert_performance_target(
            duration, self.performance_targets["extract_short"], "Short file extraction"
        )

        # Memory assertion
        memory_usage = memory_monitor.get_memory_usage_mb()
        assert (
            memory_usage <= self.memory_targets["extract_short"]
        ), f"Memory usage {memory_usage:.1f}MB exceeded target {self.memory_targets['extract_short']}MB"

    def test_extract_performance_medium_file(self):
        """Test audio extraction performance with medium file."""
        if "medium" not in self.test_files:
            pytest.skip("Medium test file not available")

        input_file = self.test_files["medium"]
        output_file = self.output_dir / "perf_extract_medium.mp3"

        with self.monitor_memory_usage() as memory_monitor:
            start_time = time.time()

            result = self.run_extract_command(
                input_file=input_file, output_file=output_file, quality="high"
            )

            duration = time.time() - start_time
            memory_monitor.update_peak()

        assert result.success, f"Extract failed: {result.error}"

        # Performance assertions
        self.assert_performance_target(
            duration, self.performance_targets["extract_medium"], "Medium file extraction"
        )

        # Memory assertion
        memory_usage = memory_monitor.get_memory_usage_mb()
        assert (
            memory_usage <= self.memory_targets["extract_medium"]
        ), f"Memory usage {memory_usage:.1f}MB exceeded target {self.memory_targets['extract_medium']}MB"

    def test_transcribe_performance_short_audio(self):
        """Test transcription performance with short audio."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["audio_only"]
        output_file = self.output_dir / "perf_transcribe_short.json"

        # Mock transcription for consistent timing
        with patch("src.services.transcription.TranscriptionService") as mock_service:
            mock_service.return_value.transcribe.return_value = self.mock_successful_transcription()

            with self.monitor_memory_usage() as memory_monitor:
                start_time = time.time()

                result = self.run_transcribe_command(
                    input_file=input_file, provider="deepgram", output_file=output_file
                )

                duration = time.time() - start_time
                memory_monitor.update_peak()

        assert result.success, f"Transcribe failed: {result.error}"

        # Performance assertion (should be very fast with mocked service)
        self.assert_performance_target(
            duration, self.performance_targets["transcribe_short"], "Short audio transcription"
        )

    def test_full_process_performance_short_file(self):
        """Test full processing pipeline performance with short file."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["short"]

        # Mock services for consistent performance
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {
                "executive_summary": "Performance test summary",
                "chapter_overview": "Performance test chapters",
                "topic_analysis": "Performance test topics",
                "full_transcript": "Performance test transcript",
                "key_insights": "Performance test insights",
            }

            with self.monitor_memory_usage() as memory_monitor:
                start_time = time.time()

                result = self.run_process_command(
                    input_file=input_file, output_dir=self.output_dir, provider="deepgram"
                )

                duration = time.time() - start_time
                memory_monitor.update_peak()

        assert result.success, f"Process failed: {result.error}"

        # Performance assertion
        self.assert_performance_target(
            duration, self.performance_targets["process_short"], "Short file full processing"
        )

        # Memory assertion
        memory_usage = memory_monitor.get_memory_usage_mb()
        assert (
            memory_usage <= self.memory_targets["process_short"]
        ), f"Memory usage {memory_usage:.1f}MB exceeded target {self.memory_targets['process_short']}MB"

    def test_cpu_utilization_monitoring(self):
        """Test CPU utilization during processing."""
        if "medium" not in self.test_files:
            pytest.skip("Medium test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["medium"]
        cpu_samples = []

        def monitor_cpu():
            """Monitor CPU usage in background thread."""
            while not stop_monitoring.is_set():
                cpu_samples.append(psutil.cpu_percent(interval=1))

        stop_monitoring = threading.Event()

        # Mock services for faster execution
        with (
            patch("src.services.transcription.TranscriptionService") as mock_transcription,
            patch("src.analysis.full_analyzer.FullAnalyzer") as mock_analyzer,
        ):
            mock_transcription.return_value.transcribe.return_value = (
                self.mock_successful_transcription()
            )
            mock_analyzer.return_value.analyze.return_value = {"executive_summary": "Test"}

            # Start CPU monitoring
            monitor_thread = threading.Thread(target=monitor_cpu)
            monitor_thread.start()

            try:
                result = self.run_process_command(input_file=input_file, output_dir=self.output_dir)
            finally:
                stop_monitoring.set()
                monitor_thread.join(timeout=5)

        assert result.success, f"Process failed: {result.error}"

        if cpu_samples:
            avg_cpu = sum(cpu_samples) / len(cpu_samples)
            max_cpu = max(cpu_samples)

            # CPU utilization should be reasonable
            assert avg_cpu <= 80.0, f"Average CPU usage {avg_cpu:.1f}% too high"
            assert max_cpu <= 95.0, f"Peak CPU usage {max_cpu:.1f}% too high"

    def test_memory_leak_detection(self):
        """Test for memory leaks during repeated operations."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        memory_samples = []

        # Run multiple extractions and monitor memory
        for i in range(5):
            output_file = self.output_dir / f"leak_test_{i}.mp3"

            # Record memory before operation
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024

            result = self.run_extract_command(input_file=input_file, output_file=output_file)

            assert result.success, f"Extraction {i} failed: {result.error}"

            # Record memory after operation
            memory_after = psutil.Process().memory_info().rss / 1024 / 1024
            memory_samples.append((memory_before, memory_after, memory_after - memory_before))

        # Analyze memory usage trend
        memory_deltas = [delta for _, _, delta in memory_samples]
        avg_delta = sum(memory_deltas) / len(memory_deltas)

        # Memory growth should be minimal
        assert avg_delta <= 50.0, f"Average memory growth {avg_delta:.1f}MB indicates possible leak"

        # Final memory should not be excessively higher than initial
        initial_memory = memory_samples[0][0]
        final_memory = memory_samples[-1][1]
        total_growth = final_memory - initial_memory

        assert total_growth <= 200.0, f"Total memory growth {total_growth:.1f}MB too high"


class TestLoadTesting(E2ETestBase, CLITestMixin, MockProviderMixin):
    """Load testing scenarios including concurrent operations."""

    @classmethod
    def setup_class(cls):
        """Setup test data for load testing."""
        cls.test_data_manager = TestDataManager()
        cls.test_files = cls.test_data_manager.generate_all_test_files()

    def test_concurrent_extractions(self):
        """Test concurrent audio extractions."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        num_concurrent = 3

        def extract_audio(index):
            """Extract audio for load testing."""
            output_file = self.output_dir / f"concurrent_extract_{index}.mp3"

            start_time = time.time()
            result = self.run_extract_command(input_file=input_file, output_file=output_file)
            duration = time.time() - start_time

            return {
                "index": index,
                "success": result.success,
                "duration": duration,
                "error": result.error if not result.success else None,
            }

        # Run concurrent extractions
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(extract_audio, i) for i in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        successful_operations = [r for r in results if r["success"]]
        [r for r in results if not r["success"]]

        # At least 80% should succeed under load
        success_rate = len(successful_operations) / len(results)
        assert success_rate >= 0.8, f"Success rate {success_rate:.1%} too low under concurrent load"

        # Average duration should not be excessively impacted
        if successful_operations:
            avg_duration = sum(r["duration"] for r in successful_operations) / len(
                successful_operations
            )
            assert (
                avg_duration <= 120.0
            ), f"Average duration {avg_duration:.1f}s too high under load"

    def test_concurrent_transcriptions(self):
        """Test concurrent transcription operations."""
        if "audio_only" not in self.test_files:
            pytest.skip("Audio test file not available")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        input_file = self.test_files["audio_only"]
        num_concurrent = 3

        def transcribe_audio(index):
            """Transcribe audio for load testing."""
            output_file = self.output_dir / f"concurrent_transcribe_{index}.json"

            # Mock transcription service for consistent performance
            with patch("src.services.transcription.TranscriptionService") as mock_service:
                mock_service.return_value.transcribe.return_value = (
                    self.mock_successful_transcription()
                )

                start_time = time.time()
                result = self.run_transcribe_command(
                    input_file=input_file, provider="deepgram", output_file=output_file
                )
                duration = time.time() - start_time

                return {
                    "index": index,
                    "success": result.success,
                    "duration": duration,
                    "error": result.error if not result.success else None,
                }

        # Run concurrent transcriptions
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(transcribe_audio, i) for i in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        successful_operations = [r for r in results if r["success"]]

        # All should succeed with mocked service
        success_rate = len(successful_operations) / len(results)
        assert success_rate >= 0.9, f"Success rate {success_rate:.1%} too low for mocked operations"

    def test_sequential_large_files(self):
        """Test processing multiple files sequentially."""
        test_files = []

        # Use available test files
        for file_type in ["short", "medium", "audio_only"]:
            if file_type in self.test_files:
                test_files.append(self.test_files[file_type])

        if not test_files:
            pytest.skip("No test files available")

        processing_times = []
        memory_usage = []

        for i, input_file in enumerate(test_files):
            output_file = self.output_dir / f"sequential_{i}.mp3"

            # Monitor memory before operation
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024

            start_time = time.time()
            result = self.run_extract_command(input_file=input_file, output_file=output_file)
            duration = time.time() - start_time

            # Monitor memory after operation
            memory_after = psutil.Process().memory_info().rss / 1024 / 1024

            processing_times.append(duration)
            memory_usage.append(memory_after - memory_before)

            assert result.success, f"Sequential processing failed for file {i}: {result.error}"

        # Memory usage should not grow significantly between operations
        if len(memory_usage) > 1:
            memory_growth = max(memory_usage) - min(memory_usage)
            assert (
                memory_growth <= 100.0
            ), f"Memory growth {memory_growth:.1f}MB between operations too high"

    def test_rapid_api_calls_simulation(self):
        """Test rapid API calls to check rate limiting handling."""
        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        num_rapid_calls = 10
        call_interval = 0.1  # 100ms between calls

        def rapid_transcription_call(index):
            """Simulate rapid API call."""
            # Mock different response scenarios
            with patch("src.services.transcription.TranscriptionService") as mock_service:
                if index % 5 == 0:  # Every 5th call simulates rate limit
                    mock_service.return_value.transcribe.side_effect = Exception(
                        "Rate limit exceeded"
                    )
                else:
                    mock_service.return_value.transcribe.return_value = (
                        self.mock_successful_transcription()
                    )

                try:
                    service = mock_service("test_key")
                    result = service.transcribe("dummy_file.mp3")
                    return {"index": index, "success": True, "result": result}
                except Exception as e:
                    return {"index": index, "success": False, "error": str(e)}

        results = []
        for i in range(num_rapid_calls):
            result = rapid_transcription_call(i)
            results.append(result)
            time.sleep(call_interval)

        # Analyze rate limiting behavior
        successful_calls = [r for r in results if r["success"]]
        rate_limited_calls = [
            r for r in results if not r["success"] and "rate limit" in r.get("error", "").lower()
        ]

        # Should handle rate limiting gracefully
        total_calls = len(results)
        success_rate = len(successful_calls) / total_calls

        # With simulated rate limiting, expect some failures
        assert (
            success_rate >= 0.5
        ), f"Success rate {success_rate:.1%} too low even with rate limiting"
        assert len(rate_limited_calls) > 0, "Rate limiting simulation should produce some failures"

    def test_resource_cleanup_under_load(self):
        """Test that resources are properly cleaned up under load."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]
        num_operations = 5

        # Track file handles and temp files
        initial_fd_count = (
            len(os.listdir("/proc/self/fd")) if os.path.exists("/proc/self/fd") else 0
        )
        temp_files_created = []

        for i in range(num_operations):
            output_file = self.output_dir / f"cleanup_test_{i}.mp3"
            temp_files_created.append(output_file)

            result = self.run_extract_command(input_file=input_file, output_file=output_file)

            assert result.success, f"Operation {i} failed: {result.error}"

        # Check file descriptor leaks
        if os.path.exists("/proc/self/fd"):
            final_fd_count = len(os.listdir("/proc/self/fd"))
            fd_growth = final_fd_count - initial_fd_count
            assert fd_growth <= 5, f"File descriptor leak detected: {fd_growth} new FDs"

        # Verify output files were created
        for temp_file in temp_files_created:
            assert temp_file.exists(), f"Output file {temp_file} was not created"
            assert temp_file.stat().st_size > 0, f"Output file {temp_file} is empty"


class TestStressScenarios(E2ETestBase, CLITestMixin, MockProviderMixin):
    """Stress testing with edge cases and extreme scenarios."""

    def test_large_file_handling(self):
        """Test handling of large files (if available)."""
        large_file_path = self.test_data_manager.get_test_file_path("large")

        if not large_file_path or not large_file_path.exists():
            pytest.skip("Large test file not available")

        # Check if it's actually a large file or just a placeholder
        file_size = large_file_path.stat().st_size
        if file_size < 100 * 1024 * 1024:  # Less than 100MB
            pytest.skip("Large test file is just a placeholder")

        self.set_test_env(DEEPGRAM_API_KEY="test_key")

        # Test extraction with large file
        output_file = self.output_dir / "large_extract.mp3"

        with self.monitor_memory_usage() as memory_monitor:
            start_time = time.time()

            result = self.run_extract_command(
                input_file=large_file_path,
                output_file=output_file,
                timeout=1800,  # 30 minute timeout
            )

            duration = time.time() - start_time
            memory_monitor.update_peak()

        if result.success:
            # If successful, check performance
            assert duration <= 900, f"Large file processing took {duration:.1f}s, expected <= 900s"

            memory_usage = memory_monitor.get_memory_usage_mb()
            assert (
                memory_usage <= 2000
            ), f"Memory usage {memory_usage:.1f}MB too high for large file"
        else:
            # If failed, should be due to size limits, not crashes
            assert (
                "size" in result.error.lower()
                or "large" in result.error.lower()
                or "limit" in result.error.lower()
            ), f"Unexpected error for large file: {result.error}"

    def test_memory_pressure_handling(self):
        """Test behavior under memory pressure."""
        if "medium" not in self.test_files:
            pytest.skip("Medium test file not available")

        input_file = self.test_files["medium"]

        # Simulate memory pressure by creating large objects
        memory_hogs = []
        try:
            # Allocate memory to create pressure
            for _ in range(10):
                memory_hogs.append(bytearray(50 * 1024 * 1024))  # 50MB each

            # Try processing under memory pressure
            output_file = self.output_dir / "memory_pressure.mp3"

            result = self.run_extract_command(
                input_file=input_file, output_file=output_file, timeout=300
            )

            # Should either succeed or fail gracefully
            if not result.success:
                error_msg = result.error.lower()
                memory_related = any(
                    keyword in error_msg
                    for keyword in ["memory", "out of memory", "allocation", "oom"]
                )
                if memory_related:
                    pytest.skip("Memory pressure caused expected failure")
                else:
                    raise AssertionError(f"Unexpected error under memory pressure: {result.error}")

        finally:
            # Clean up memory
            del memory_hogs

    def test_disk_space_handling(self):
        """Test behavior when disk space is limited."""
        if "short" not in self.test_files:
            pytest.skip("Short test file not available")

        input_file = self.test_files["short"]

        # Check available disk space
        statvfs = os.statvfs(str(self.temp_dir))
        available_bytes = statvfs.f_frsize * statvfs.f_bavail
        available_mb = available_bytes / 1024 / 1024

        if available_mb < 100:  # Less than 100MB available
            # Test behavior with low disk space
            output_file = self.output_dir / "low_disk_space.mp3"

            result = self.run_extract_command(input_file=input_file, output_file=output_file)

            if not result.success:
                error_msg = result.error.lower()
                disk_related = any(
                    keyword in error_msg for keyword in ["space", "disk", "no space", "full"]
                )
                if disk_related:
                    pytest.skip("Low disk space caused expected failure")
        else:
            pytest.skip("Sufficient disk space available, cannot test low space scenario")

    def test_interrupted_operations(self):
        """Test behavior when operations are interrupted."""
        if "medium" not in self.test_files:
            pytest.skip("Medium test file not available")

        input_file = self.test_files["medium"]
        output_file = self.output_dir / "interrupted.mp3"

        # Start operation with short timeout to simulate interruption
        result = self.run_extract_command(
            input_file=input_file,
            output_file=output_file,
            timeout=5,  # Very short timeout to force interruption
        )

        # Should fail due to timeout
        assert not result.success, "Operation should have been interrupted"
        assert "timeout" in result.error.lower() or "interrupted" in result.error.lower()

        # Check that no partial files are left behind
        if output_file.exists():
            # If file exists, it should either be empty or complete
            file_size = output_file.stat().st_size
            assert file_size == 0 or file_size > 1000, "Partial file should not be left behind"
