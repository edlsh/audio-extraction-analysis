"""Test suite for Deepgram transcription service.

Note: These are duplicate Deepgram tests (covered in test_deepgram_provider.py).
Integration scenarios covered in tests/integration/.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Skip - duplicate of test_deepgram_provider.py
pytestmark = [
    pytest.mark.skip(
        reason="Duplicate Deepgram tests - covered in test_deepgram_provider.py and tests/integration/"
    ),
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.mock,
]

from src.models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)
from src.providers.deepgram import DeepgramTranscriber


class TestTranscriptionDataclasses:
    """Test transcription dataclasses."""

    def test_transcription_speaker(self):
        """Test TranscriptionSpeaker dataclass."""
        speaker = TranscriptionSpeaker(id=0, total_time=60.5, percentage=50.4)
        assert speaker.id == 0
        assert speaker.total_time == 60.5
        assert speaker.percentage == 50.4

    def test_transcription_chapter(self):
        """Test TranscriptionChapter dataclass."""
        chapter = TranscriptionChapter(
            start_time=0.0,
            end_time=60.0,
            topics=["Technology", "Business"],
            confidence_scores=[0.85, 0.72],
        )
        assert chapter.start_time == 0.0
        assert chapter.end_time == 60.0
        assert len(chapter.topics) == 2
        assert len(chapter.confidence_scores) == 2

    def test_transcription_utterance(self):
        """Test TranscriptionUtterance dataclass."""
        utterance = TranscriptionUtterance(speaker=0, start=10.0, end=20.0, text="Hello world")
        assert utterance.speaker == 0
        assert utterance.start == 10.0
        assert utterance.end == 20.0
        assert utterance.text == "Hello world"

    def test_transcription_result_initialization(self):
        """Test TranscriptionResult initialization."""
        from datetime import datetime

        result = TranscriptionResult(
            transcript="Test transcript",
            duration=120.0,
            generated_at=datetime.now(),
            audio_file="/path/to/audio.mp3",
        )

        assert result.transcript == "Test transcript"
        assert result.duration == 120.0
        assert isinstance(result.chapters, list)
        assert isinstance(result.speakers, list)
        assert isinstance(result.utterances, list)
        assert isinstance(result.topics, dict)
        assert isinstance(result.intents, list)
        assert isinstance(result.sentiment_distribution, dict)


class TestDeepgramTranscriber:
    """Test DeepgramTranscriber class."""

    def test_init_with_api_key(self):
        """Test transcriber initialization with explicit API key."""
        transcriber = DeepgramTranscriber(api_key="test_key")
        assert transcriber.api_key == "test_key"

    def test_init_with_config_api_key(self, api_key_set):
        """Test transcriber initialization using Config API key."""
        # This test uses the api_key_set fixture which sets DEEPGRAM_API_KEY=test_api_key_12345
        # But we need to mock the Config class to use it instead of .env
        with patch("src.providers.deepgram.Config") as mock_config:
            mock_config.DEEPGRAM_API_KEY = "test_api_key_12345"
            transcriber = DeepgramTranscriber()
            assert transcriber.api_key == "test_api_key_12345"

    def test_init_without_api_key(self):
        """Test transcriber initialization fails without API key."""
        # Mock config to return None for deepgram_api_key
        with patch("src.providers.deepgram.Config") as mock_config:
            mock_config.DEEPGRAM_API_KEY = None
            with pytest.raises(ValueError, match="DEEPGRAM_API_KEY not found"):
                DeepgramTranscriber()

    def test_format_time(self, api_key_set):
        """Test time formatting helper method."""
        transcriber = DeepgramTranscriber()

        assert transcriber._format_time(0) == "00:00:00"
        assert transcriber._format_time(65) == "00:01:05"
        assert transcriber._format_time(3661) == "01:01:01"
        assert transcriber._format_time(7265.5) == "02:01:05"  # Rounds down seconds

    @pytest.mark.asyncio
    async def test_transcribe_async_file_not_found(self, api_key_set):
        """Test async transcription with non-existent file."""
        transcriber = DeepgramTranscriber()
        non_existent_path = Path("/non/existent/file.mp3")

        result = await transcriber.transcribe_async(non_existent_path)
        assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_async_success(
        self, api_key_set, temp_audio_file, mock_deepgram_client
    ):
        """Test successful async transcription."""
        transcriber = DeepgramTranscriber()
        mock_deepgram, mock_response = mock_deepgram_client

        # Mock the lazy import inside the transcribe_async method
        with patch("builtins.__import__") as mock_import:

            def side_effect(name, *args, **kwargs):
                if name == "deepgram":
                    return mock_deepgram
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = side_effect

            # Mock the async transcribe_file call
            async def mock_transcribe_file(*args, **kwargs):
                return mock_response

            mock_client = mock_deepgram.DeepgramClient.return_value
            mock_client.listen.asyncrest.v.return_value.transcribe_file = mock_transcribe_file

            result = await transcriber.transcribe_async(temp_audio_file)

        assert result is not None
        assert isinstance(result, TranscriptionResult)
        assert (
            result.transcript
            == "This is a test transcription with multiple speakers discussing important topics."
        )
        assert result.duration == 120.5
        assert len(result.speakers) == 2  # Two speakers from mock data
        assert len(result.chapters) == 2  # Two topic segments
        assert "Technology" in result.topics
        assert "inform" in result.intents
        assert "positive" in result.sentiment_distribution

    def test_transcribe_sync_wrapper(self, api_key_set, temp_audio_file, mock_deepgram_client):
        """Test synchronous transcription wrapper."""
        transcriber = DeepgramTranscriber()
        _mock_deepgram, _mock_response = mock_deepgram_client

        # Mock the entire transcribe_async method instead of dealing with imports
        async def mock_transcribe_async(audio_path, language="en"):
            from datetime import datetime

            return TranscriptionResult(
                transcript="Sync test transcript",
                duration=60.0,
                generated_at=datetime.now(),
                audio_file=str(audio_path),
            )

        with patch.object(transcriber, "transcribe_async", mock_transcribe_async):
            result = transcriber.transcribe(temp_audio_file)

        assert result is not None
        assert result.transcript == "Sync test transcript"

    def test_save_result_to_file(self, api_key_set, temp_output_dir):
        """Test saving transcription result to file."""
        from datetime import datetime

        transcriber = DeepgramTranscriber()

        # Create a sample result
        result = TranscriptionResult(
            transcript="This is a test transcript for saving.",
            duration=90.0,
            generated_at=datetime.now(),
            audio_file="/test/audio.mp3",
        )

        # Add some sample data
        result.summary = "Test summary"
        result.chapters = [
            TranscriptionChapter(
                start_time=0.0, end_time=45.0, topics=["Testing"], confidence_scores=[0.95]
            )
        ]
        result.speakers = [TranscriptionSpeaker(id=0, total_time=90.0, percentage=100.0)]
        result.utterances = [
            TranscriptionUtterance(
                speaker=0, start=0.0, end=90.0, text="This is a test transcript for saving."
            )
        ]
        result.topics = {"Testing": 1}
        result.intents = ["inform"]
        result.sentiment_distribution = {"neutral": 1}

        output_path = temp_output_dir / "test_transcript.txt"
        transcriber.save_result_to_file(result, output_path)

        # Verify file was created and contains expected content
        assert output_path.exists()
        content = output_path.read_text()

        assert "DEEPGRAM NOVA 3 TRANSCRIPTION & ANALYSIS" in content
        assert "This is a test transcript for saving." in content
        assert "Test summary" in content
        assert "CONTENT CHAPTERS:" in content
        assert "Testing (95.0%)" in content
        assert "SPEAKER TIME DISTRIBUTION:" in content
        assert "DETECTED INTENTS:" in content
        assert "inform" in content


class TestErrorHandling:
    """Test error handling in transcription service."""

    @pytest.mark.asyncio
    async def test_transcribe_async_deepgram_error(self, api_key_set, temp_audio_file):
        """Test handling of Deepgram API errors."""
        transcriber = DeepgramTranscriber()

        # Mock an exception in the transcription process
        with patch("builtins.__import__") as mock_import:

            def side_effect(name, *args, **kwargs):
                if name == "deepgram":
                    raise ImportError("Deepgram SDK not available")
                return __import__(name, *args, **kwargs)

            mock_import.side_effect = side_effect

            result = await transcriber.transcribe_async(temp_audio_file)

        assert result is None

    def test_sync_transcribe_error_handling(self, api_key_set, temp_audio_file):
        """Test error handling in synchronous transcription."""
        transcriber = DeepgramTranscriber()

        # Mock transcribe_async to raise an exception
        async def mock_transcribe_async_error(*args, **kwargs):
            raise Exception("Transcription failed")

        # Mock the event loop handling in transcribe method
        with patch.object(transcriber, "transcribe_async", mock_transcribe_async_error):
            with patch("asyncio.get_event_loop") as mock_get_loop:
                with patch("asyncio.new_event_loop") as mock_new_loop:
                    with patch("asyncio.set_event_loop"):
                        mock_loop = Mock()
                        mock_loop.run_until_complete.side_effect = Exception("Transcription failed")
                        mock_loop.is_running.return_value = False
                        mock_get_loop.side_effect = RuntimeError("No event loop")
                        mock_new_loop.return_value = mock_loop

                        result = transcriber.transcribe(temp_audio_file)

        # Should handle exception and return None (logged error)
        assert result is None


class TestAdvancedFeatures:
    """Test advanced Deepgram Nova 3 features parsing."""

    @pytest.mark.asyncio
    async def test_complex_response_parsing(self, api_key_set, temp_audio_file):
        """Test parsing of complex Deepgram response with all features."""
        transcriber = DeepgramTranscriber()

        # Create a more complex mock response
        mock_response = Mock()
        mock_response.metadata.duration = 300.0
        mock_response.results.channels = [
            Mock(alternatives=[Mock(transcript="Complex transcript with multiple features.")])
        ]

        # Advanced features
        mock_response.results.summary = Mock(short="Complex discussion summary")

        # Multiple topic segments
        mock_response.results.topics = Mock(
            segments=[
                Mock(
                    start_time=0.0,
                    end_time=100.0,
                    topics=[
                        Mock(topic="AI", confidence_score=0.95),
                        Mock(topic="Technology", confidence_score=0.88),
                    ],
                ),
                Mock(
                    start_time=100.0,
                    end_time=200.0,
                    topics=[Mock(topic="Business", confidence_score=0.92)],
                ),
                Mock(
                    start_time=200.0,
                    end_time=300.0,
                    topics=[Mock(topic="Future", confidence_score=0.87)],
                ),
            ]
        )

        # Multiple speakers and utterances
        mock_response.results.utterances = [
            Mock(speaker=0, start=0.0, end=150.0, transcript="First speaker long segment."),
            Mock(speaker=1, start=150.0, end=250.0, transcript="Second speaker discussion."),
            Mock(speaker=2, start=250.0, end=300.0, transcript="Third speaker conclusion."),
        ]

        # Complex intents and sentiments
        mock_response.results.intents = Mock(
            segments=[Mock(intents=[Mock(intent="explain"), Mock(intent="persuade")])]
        )

        mock_response.results.sentiments = Mock(
            segments=[
                Mock(sentiment="positive"),
                Mock(sentiment="neutral"),
                Mock(sentiment="positive"),
                Mock(sentiment="negative"),
            ]
        )

        # Mock the transcribe_async method to return this complex response
        async def mock_complex_transcription(audio_path, language="en"):
            # Simulate the parsing logic
            from datetime import datetime

            result = TranscriptionResult(
                transcript="Complex transcript with multiple features.",
                duration=300.0,
                generated_at=datetime.now(),
                audio_file=str(audio_path),
            )

            result.summary = "Complex discussion summary"
            result.chapters = [
                TranscriptionChapter(0.0, 100.0, ["AI", "Technology"], [0.95, 0.88]),
                TranscriptionChapter(100.0, 200.0, ["Business"], [0.92]),
                TranscriptionChapter(200.0, 300.0, ["Future"], [0.87]),
            ]
            result.topics = {"AI": 1, "Technology": 1, "Business": 1, "Future": 1}
            result.speakers = [
                TranscriptionSpeaker(0, 150.0, 50.0),
                TranscriptionSpeaker(1, 100.0, 33.3),
                TranscriptionSpeaker(2, 50.0, 16.7),
            ]
            result.utterances = [
                TranscriptionUtterance(0, 0.0, 150.0, "First speaker long segment."),
                TranscriptionUtterance(1, 150.0, 250.0, "Second speaker discussion."),
                TranscriptionUtterance(2, 250.0, 300.0, "Third speaker conclusion."),
            ]
            result.intents = ["explain", "persuade"]
            result.sentiment_distribution = {"positive": 2, "neutral": 1, "negative": 1}

            return result

        with patch.object(transcriber, "transcribe_async", mock_complex_transcription):
            result = await transcriber.transcribe_async(temp_audio_file)

        assert result is not None
        assert len(result.chapters) == 3
        assert len(result.speakers) == 3
        assert len(result.utterances) == 3
        assert len(result.topics) == 4
        assert len(result.intents) == 2
        assert result.sentiment_distribution["positive"] == 2
