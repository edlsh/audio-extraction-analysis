"""Unit tests for TranscriptionService progress tracking functionality.

This module tests the progress tracking capabilities of the TranscriptionService,
including the existence and availability of methods responsible for:
- Progress callback integration during transcription
- Provider speed estimation for progress calculation
- Sigmoid-based progress curve modeling
"""

from src.services.transcription import TranscriptionService


class TestTranscriptionServiceProgress:
    """Test suite for verifying TranscriptionService progress functionality.

    These tests verify the existence of critical methods required for progress
    tracking during transcription operations. The tests use basic existence
    checks to ensure the service interface is complete before integration testing.
    """

    def test_import_works(self):
        """Verify TranscriptionService can be instantiated successfully.

        This basic smoke test ensures the service class is properly importable
        and can be instantiated without errors, which is a prerequisite for
        all other progress functionality tests.
        """
        service = TranscriptionService()
        assert service is not None

    def test_transcribe_with_progress_method_exists(self):
        """Verify the transcribe_with_progress method is available.

        This test confirms that the main entry point for progress-enabled
        transcription exists in the service interface. This method accepts
        a callback function to report transcription progress to callers.
        """
        service = TranscriptionService()
        assert hasattr(service, "transcribe_with_progress")

    def test_get_provider_speed_method_exists(self):
        """Verify the _get_provider_speed private method is available.

        This test ensures the internal method for estimating transcription speed
        based on the selected provider exists. Speed estimation is used to
        calculate realistic progress percentages during transcription operations.
        """
        service = TranscriptionService()
        assert hasattr(service, "_get_provider_speed")

    def test_calculate_sigmoid_progress_method_exists(self):
        """Verify the _calculate_sigmoid_progress private method is available.

        This test confirms the existence of the sigmoid curve calculation method,
        which provides smooth, non-linear progress updates that prevent the
        progress indicator from appearing stuck at extremes (0% or 100%).
        """
        service = TranscriptionService()
        assert hasattr(service, "_calculate_sigmoid_progress")
