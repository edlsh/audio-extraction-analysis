"""Pytest configuration and shared fixtures for unit tests.

This module provides common test fixtures for the audio extraction and analysis test suite,
including mocked Deepgram API clients, temporary file creation utilities, and FFmpeg mocks.

Key Fixtures:
    - clear_deepgram_env: Ensures clean environment state for each test
    - mock_deepgram_client: Comprehensive Deepgram API response mock
    - temp_audio_file/temp_video_file: Temporary test media files
    - mock_ffmpeg: Mock for subprocess FFmpeg calls
    - api_key_set: Mock API key configuration
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def clear_deepgram_env(monkeypatch):
    """Ensure DEEPGRAM_API_KEY environment variable is absent by default.

    This auto-use fixture runs before each test to guarantee a clean environment state.
    Individual tests can explicitly set the API key if needed using monkeypatch.setenv().

    Args:
        monkeypatch: Pytest's monkeypatch fixture for modifying environment variables.
    """
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)


@pytest.fixture
def mock_deepgram_client(monkeypatch):
    """Provide a comprehensive mock of the Deepgram API client and response structure.

    This fixture creates a fully-mocked Deepgram client with realistic response data
    matching the Deepgram Nova 3 API structure. It prevents external API calls during
    testing while providing all the necessary response attributes for feature extraction.

    The mock includes:
        - Metadata (duration, channels)
        - Transcription results (transcript, paragraphs, sentences)
        - Summary (short summary text)
        - Topics (time-segmented topics with confidence scores)
        - Intents (detected speaker intents)
        - Sentiments (segment-level sentiment analysis)
        - Utterances (speaker-diarized transcripts with timestamps)

    Returns:
        tuple: (mock_deepgram_module, mock_response) where:
            - mock_deepgram_module: Mock of the Deepgram SDK module with ClientOptionsFromEnv,
              DeepgramClient, and PrerecordedOptions
            - mock_response: Mock response object matching Deepgram API structure

    Note:
        The returned mock_deepgram_module should be patched in individual tests
        since the Deepgram import is lazy-loaded in the transcription service.
    """

    # Mock response data structure matching Deepgram Nova 3 API format
    mock_response_data = {
        "metadata": {"duration": 120.5, "channels": 1},
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": (
                                "This is a test transcription with multiple speakers "
                                "discussing important topics."
                            ),
                            "paragraphs": {
                                "paragraphs": [
                                    {
                                        "sentences": [
                                            {
                                                "text": (
                                                    "This is a test transcription with "
                                                    "multiple speakers discussing important topics."
                                                )
                                            }
                                        ]
                                    }
                                ]
                            },
                        }
                    ]
                }
            ],
            "summary": {"short": "A discussion about important topics between multiple speakers."},
            "topics": {
                "segments": [
                    {
                        "start_time": 0.0,
                        "end_time": 60.0,
                        "topics": [
                            {"topic": "Technology", "confidence_score": 0.85},
                            {"topic": "Business", "confidence_score": 0.72},
                        ],
                    },
                    {
                        "start_time": 60.0,
                        "end_time": 120.5,
                        "topics": [{"topic": "Innovation", "confidence_score": 0.91}],
                    },
                ]
            },
            "intents": {"segments": [{"intents": [{"intent": "inform"}, {"intent": "question"}]}]},
            "sentiments": {
                "segments": [
                    {"sentiment": "positive"},
                    {"sentiment": "neutral"},
                    {"sentiment": "positive"},
                ]
            },
            "utterances": [
                {
                    "speaker": 0,
                    "start": 0.0,
                    "end": 30.0,
                    "transcript": "This is the first speaker talking about technology.",
                },
                {
                    "speaker": 1,
                    "start": 30.0,
                    "end": 90.0,
                    "transcript": "This is the second speaker discussing business innovations.",
                },
                {
                    "speaker": 0,
                    "start": 90.0,
                    "end": 120.5,
                    "transcript": "First speaker concluding the discussion.",
                },
            ],
        },
    }

    # Create mock response object with nested attribute access matching Deepgram SDK structure
    mock_response = Mock()

    # Mock metadata attributes (duration, channel count)
    mock_response.metadata.duration = mock_response_data["metadata"]["duration"]

    # Mock transcription results with channels, alternatives, and paragraph structure
    mock_response.results.channels = [
        Mock(
            alternatives=[
                Mock(
                    transcript=mock_response_data["results"]["channels"][0]["alternatives"][0][
                        "transcript"
                    ],
                    paragraphs=Mock(
                        paragraphs=[
                            Mock(
                                sentences=[
                                    Mock(
                                        text=(
                                            "This is a test transcription with multiple speakers "
                                            "discussing important topics."
                                        )
                                    )
                                ]
                            )
                        ]
                    ),
                )
            ]
        )
    ]

    # Mock summary feature (short-form summary generation)
    mock_response.results.summary = Mock()
    mock_response.results.summary.short = mock_response_data["results"]["summary"]["short"]

    # Mock topic detection with time-segmented topics and confidence scores
    mock_topics = Mock()
    mock_topics.segments = [
        Mock(
            start_time=seg["start_time"],
            end_time=seg["end_time"],
            topics=[
                Mock(topic=t["topic"], confidence_score=t["confidence_score"])
                for t in seg["topics"]
            ],
        )
        for seg in mock_response_data["results"]["topics"]["segments"]
    ]
    mock_response.results.topics = mock_topics

    # Mock intent detection (speaker intent classification)
    mock_intents = Mock()
    mock_intents.segments = [
        Mock(intents=[Mock(intent=i["intent"]) for i in seg["intents"]])
        for seg in mock_response_data["results"]["intents"]["segments"]
    ]
    mock_response.results.intents = mock_intents

    # Mock sentiment analysis (positive/neutral/negative classification per segment)
    mock_sentiments = Mock()
    mock_sentiments.segments = [
        Mock(sentiment=seg["sentiment"])
        for seg in mock_response_data["results"]["sentiments"]["segments"]
    ]
    mock_response.results.sentiments = mock_sentiments

    # Mock speaker diarization utterances (speaker-separated transcripts with timestamps)
    mock_utterances = [
        Mock(
            speaker=utt["speaker"], start=utt["start"], end=utt["end"], transcript=utt["transcript"]
        )
        for utt in mock_response_data["results"]["utterances"]
    ]
    mock_response.results.utterances = mock_utterances

    # Mock the Deepgram client with chained method calls for transcription
    mock_client = Mock()
    mock_client.listen.asyncrest.v.return_value.transcribe_file.return_value = mock_response

    # Mock the Deepgram SDK module with all required classes
    mock_deepgram = Mock()
    mock_deepgram.ClientOptionsFromEnv = Mock(return_value=Mock())
    mock_deepgram.DeepgramClient = Mock(return_value=mock_client)
    mock_deepgram.PrerecordedOptions = Mock()

    # Helper function for lazy import mocking (not used directly in this fixture)
    def mock_import():
        return (
            mock_deepgram.ClientOptionsFromEnv,
            mock_deepgram.DeepgramClient,
            mock_deepgram.PrerecordedOptions,
        )

    return mock_deepgram, mock_response


@pytest.fixture
def temp_audio_file():
    """Create a temporary audio file for testing audio processing functions.

    Creates a temporary .mp3 file with dummy byte content (not actual audio data).
    The file is automatically cleaned up after the test completes.

    Yields:
        Path: Path object pointing to the temporary audio file.

    Example:
        def test_audio_processing(temp_audio_file):
            result = process_audio(temp_audio_file)
            assert result is not None
    """
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        # Write dummy byte content (not valid audio, but sufficient for path/file handling tests)
        temp_file.write(b"fake_audio_data" * 1000)
        temp_path = Path(temp_file.name)

    yield temp_path

    # Cleanup: Remove the temporary audio file after test completion
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture(scope="session")
def temp_video_file(tmp_path_factory, ffmpeg_binary):
    """Generate a minimal valid MP4 test video file (session-scoped for performance).

    Creates a real video file using FFmpeg with minimal duration (2 seconds) for testing.
    This ensures the video file is valid and can be processed by FFmpeg-based tools.

    Args:
        tmp_path_factory: pytest temp path factory
        ffmpeg_binary: FFmpeg binary path

    Yields:
        Path: Path object pointing to the temporary video file.

    Example:
        def test_video_extraction(temp_video_file):
            audio_path = extract_audio(temp_video_file)
            assert audio_path.exists()
    """
    output_dir = tmp_path_factory.mktemp("video_fixtures")
    output = output_dir / "test_video_2s.mp4"

    # Generate 2-second test video with both video and audio streams
    result = subprocess.run([
        str(ffmpeg_binary),
        "-f", "lavfi",
        "-i", "testsrc=duration=2:size=320x240:rate=1",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        str(output)
    ], capture_output=True, check=False)

    if result.returncode != 0:
        pytest.skip(f"Failed to generate test video: {result.stderr.decode()}")

    return output


@pytest.fixture
def temp_video_file_with_brackets():
    """Create a temporary video file with special characters (square brackets) in the filename.

    This fixture tests edge cases where filenames contain characters that may require
    special handling in shell commands or FFmpeg operations. Square brackets are
    particularly important to test as they can be interpreted as glob patterns.

    Yields:
        Path: Path object pointing to a video file named "test[with_square_brackets].mp4".

    Example:
        def test_special_chars_handling(temp_video_file_with_brackets):
            # Ensures FFmpeg correctly handles filenames with brackets
            result = extract_audio(temp_video_file_with_brackets)
            assert result is not None
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create file with square brackets to test shell escaping and glob pattern handling
        video_file = Path(temp_dir) / "test[with_square_brackets].mp4"
        video_file.write_bytes(b"fake_video_data" * 2000)
        yield video_file
        # Automatic cleanup via TemporaryDirectory context manager


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing file generation and storage.

    Provides a clean temporary directory for tests that need to write output files.
    The directory and all its contents are automatically cleaned up after the test.

    Yields:
        Path: Path object pointing to the temporary directory.

    Example:
        def test_file_generation(temp_output_dir):
            output_file = temp_output_dir / "result.json"
            save_results(output_file, data)
            assert output_file.exists()
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)
        # Automatic cleanup of directory and all contents via context manager


@pytest.fixture
def mock_ffmpeg(monkeypatch):
    """Mock FFmpeg subprocess calls to prevent actual video/audio processing during tests.

    Replaces subprocess.run with a mock that simulates successful FFmpeg execution
    without actually invoking FFmpeg. The mock returns realistic output including
    duration information commonly parsed from FFmpeg stderr.

    Args:
        monkeypatch: Pytest's monkeypatch fixture for patching subprocess.run.

    Returns:
        Mock: The mock_run object that replaces subprocess.run. Can be inspected
              in tests to verify FFmpeg was called with expected arguments.

    Example:
        def test_ffmpeg_called(mock_ffmpeg, temp_video_file):
            extract_audio(temp_video_file, "output.mp3")
            assert mock_ffmpeg.called
            assert "ffmpeg" in mock_ffmpeg.call_args[0][0]
    """
    mock_run = Mock()
    # Simulate successful FFmpeg execution with typical duration output
    mock_run.return_value = Mock(returncode=0, stderr="", stdout="Duration: 00:02:00.50")

    monkeypatch.setattr("subprocess.run", mock_run)

    return mock_run


@pytest.fixture
def api_key_set(monkeypatch):
    """Set a mock Deepgram API key in the environment for tests that require authentication.

    This fixture overrides the clear_deepgram_env autouse fixture by setting a test
    API key. Use this for tests that need to verify API key handling or initialization
    logic that depends on the presence of credentials.

    Args:
        monkeypatch: Pytest's monkeypatch fixture for modifying environment variables.

    Note:
        The API key value "test_api_key_12345" is a placeholder and will not work
        with actual Deepgram API calls (which should be mocked in unit tests).

    Example:
        def test_client_initialization(api_key_set):
            client = DeepgramClient()
            assert client is not None
    """
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test_api_key_12345")
