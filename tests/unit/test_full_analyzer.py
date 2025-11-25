"""Tests for the FullAnalyzer that generates 5 markdown files."""

from datetime import datetime

from src.analysis.full_analyzer import FullAnalyzer
from src.models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)


def _make_basic_result() -> TranscriptionResult:
    return TranscriptionResult(
        transcript=(
            "This is a sample transcript. We should follow up on action items. "
            "The team will deliver next week. Planning is a priority."
        ),
        duration=120.0,
        generated_at=datetime.now(),
        audio_file="/tmp/test.mp3",
        provider_name="Deepgram Nova 3",
        provider_features=["timestamps", "speaker_diarization", "topic_detection"],
    )


def test_full_analyzer_creates_all_files(tmp_path):
    result = _make_basic_result()
    # Add rich data
    result.summary = "Executive summary of the session."
    result.chapters = [
        TranscriptionChapter(
            start_time=0.0,
            end_time=60.0,
            topics=["intro", "planning"],
            confidence_scores=[0.9, 0.7],
        ),
        TranscriptionChapter(
            start_time=60.0, end_time=120.0, topics=["execution"], confidence_scores=[0.8]
        ),
    ]
    result.speakers = [
        TranscriptionSpeaker(id=0, total_time=70.0, percentage=58.3),
        TranscriptionSpeaker(id=1, total_time=50.0, percentage=41.7),
    ]
    result.utterances = [
        TranscriptionUtterance(speaker=0, start=5.0, end=15.0, text="This is a sample transcript."),
        TranscriptionUtterance(
            speaker=1, start=65.0, end=80.0, text="We should follow up on action items."
        ),
    ]
    result.topics = {"planning": 3, "execution": 2}
    result.intents = ["inform", "decide", "inform"]
    result.sentiment_distribution = {"positive": 3, "neutral": 1}

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "video")

    # Assert all 5 files exist
    expected = [
        "01_executive_summary.md",
        "02_chapter_overview.md",
        "03_key_topics_and_intents.md",
        "04_full_transcript_with_timestamps.md",
        "05_key_insights_and_takeaways.md",
    ]
    for name in expected:
        f = tmp_path / name
        assert f.exists(), f"Missing expected file: {name}"
        content = f.read_text(encoding="utf-8")
        assert len(content) > 0


def test_full_analyzer_handles_missing_optionals(tmp_path):
    result = _make_basic_result()
    # No chapters, speakers, topics, intents, sentiments, utterances
    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "video")

    # Files exist and contain fallback copy
    summary = (tmp_path / "01_executive_summary.md").read_text(encoding="utf-8")
    assert "Executive Summary" in summary

    chapters = (tmp_path / "02_chapter_overview.md").read_text(encoding="utf-8")
    assert "No chapters identified" in chapters or "Chapter-by-Chapter Overview" in chapters

    topics = (tmp_path / "03_key_topics_and_intents.md").read_text(encoding="utf-8")
    assert "No specific topics" in topics or "Topic Frequency Analysis" in topics

    transcript_md = (tmp_path / "04_full_transcript_with_timestamps.md").read_text(encoding="utf-8")
    assert "Full Transcript" in transcript_md

    insights = (tmp_path / "05_key_insights_and_takeaways.md").read_text(encoding="utf-8")
    assert "Key Insights" in insights


def test_full_analyzer_returns_correct_paths(tmp_path):
    """Test that analyze_and_save returns correct dictionary of file paths."""
    result = _make_basic_result()
    analyzer = FullAnalyzer()
    paths = analyzer.analyze_and_save(result, tmp_path, "video")

    # Verify return value structure
    assert isinstance(paths, dict)
    assert "executive_summary" in paths
    assert "chapter_overview" in paths
    assert "topics_intents" in paths
    assert "full_transcript" in paths
    assert "key_insights" in paths

    # Verify all paths are Path objects and exist
    for _key, path in paths.items():
        assert isinstance(path, type(tmp_path))
        assert path.exists()


def test_format_hms_helper():
    """Test time formatting helper method."""
    analyzer = FullAnalyzer()

    # Test various time formats
    assert analyzer._format_hms(0.0) == "00:00:00"
    assert analyzer._format_hms(59.0) == "00:00:59"
    assert analyzer._format_hms(60.0) == "00:01:00"
    assert analyzer._format_hms(3661.0) == "01:01:01"
    assert analyzer._format_hms(120.5) == "00:02:00"  # Rounds down seconds

    # Test edge cases
    assert analyzer._format_hms(-10.0) == "00:00:00"  # Negative should default to zero


def test_overall_sentiment_helper():
    """Test overall sentiment detection."""
    analyzer = FullAnalyzer()
    result = _make_basic_result()

    # Test with sentiment distribution
    result.sentiment_distribution = {"positive": 5, "neutral": 3, "negative": 1}
    assert analyzer._overall_sentiment(result) == "Positive"

    result.sentiment_distribution = {"negative": 10, "positive": 2}
    assert analyzer._overall_sentiment(result) == "Negative"

    # Test with no sentiment data
    result.sentiment_distribution = None
    assert analyzer._overall_sentiment(result) == "Unknown"

    result.sentiment_distribution = {}
    assert analyzer._overall_sentiment(result) == "Unknown"


def test_fallback_summary_helper():
    """Test fallback summary generation."""
    analyzer = FullAnalyzer()

    # Test normal case with multiple sentences
    transcript = "First sentence. Second sentence. Third sentence. Fourth sentence."
    summary = analyzer._fallback_summary(transcript)
    assert summary == "First sentence. Second sentence. Third sentence."

    # Test short transcript
    short = "Only one sentence"
    summary = analyzer._fallback_summary(short)
    assert summary == "Only one sentence"

    # Test empty transcript
    summary = analyzer._fallback_summary("")
    assert summary == "No summary available."

    # Test very long transcript (>300 chars)
    long = "A" * 400
    summary = analyzer._fallback_summary(long)
    assert len(summary) <= 304  # 300 + "..."
    assert summary.endswith("...")


def test_find_action_sentences_helper():
    """Test action sentence detection."""
    analyzer = FullAnalyzer()

    # Test with action keywords
    transcript = "We should implement this. The team will deliver next week. Nice weather today."
    actions = analyzer._find_action_sentences(transcript)
    assert len(actions) == 2
    assert "should implement" in actions[0]
    assert "will deliver" in actions[1]

    # Test with no action keywords
    no_actions = "This is a simple statement. Another statement here."
    actions = analyzer._find_action_sentences(no_actions)
    assert len(actions) == 0

    # Test empty transcript
    actions = analyzer._find_action_sentences("")
    assert len(actions) == 0


def test_approx_timestamp_for_sentence_helper():
    """Test timestamp approximation for sentences."""
    analyzer = FullAnalyzer()

    utterances = [
        TranscriptionUtterance(speaker=0, start=5.0, end=15.0, text="This is the first utterance."),
        TranscriptionUtterance(
            speaker=1, start=20.0, end=30.0, text="This is the second utterance."
        ),
    ]

    # Test matching sentence
    ts = analyzer._approx_timestamp_for_sentence("This is the first", utterances)
    assert ts == 5.0

    ts = analyzer._approx_timestamp_for_sentence("This is the second", utterances)
    assert ts == 20.0

    # Test non-matching sentence (should return 0.0)
    ts = analyzer._approx_timestamp_for_sentence("Non-existent sentence", utterances)
    assert ts == 0.0

    # Test empty utterances
    ts = analyzer._approx_timestamp_for_sentence("Any sentence", [])
    assert ts is None


def test_edge_case_empty_transcript(tmp_path):
    """Test handling of empty transcript."""
    result = TranscriptionResult(
        transcript="",
        duration=0.0,
        generated_at=datetime.now(),
        audio_file="/tmp/empty.mp3",
        provider_name="Test",
        provider_features=[],
    )

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "empty")

    # Should still create files without errors
    assert (tmp_path / "01_executive_summary.md").exists()
    summary = (tmp_path / "01_executive_summary.md").read_text(encoding="utf-8")
    assert "No summary available" in summary or "Executive Summary" in summary


def test_edge_case_zero_duration(tmp_path):
    """Test handling of zero duration."""
    result = _make_basic_result()
    result.duration = 0.0

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "zero_duration")

    summary = (tmp_path / "01_executive_summary.md").read_text(encoding="utf-8")
    assert "00:00:00" in summary


def test_chapter_percentage_calculation(tmp_path):
    """Test correct percentage calculations in chapter overview."""
    result = _make_basic_result()
    result.duration = 100.0
    result.chapters = [
        TranscriptionChapter(
            start_time=0.0, end_time=25.0, topics=["intro"], confidence_scores=[0.9]
        ),
        TranscriptionChapter(
            start_time=25.0, end_time=75.0, topics=["main"], confidence_scores=[0.8]
        ),
        TranscriptionChapter(
            start_time=75.0, end_time=100.0, topics=["outro"], confidence_scores=[0.7]
        ),
    ]

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "chapters")

    chapters_md = (tmp_path / "02_chapter_overview.md").read_text(encoding="utf-8")

    # Check percentage calculations (25%, 50%, 25%)
    assert "25.0%" in chapters_md
    assert "50.0%" in chapters_md


def test_speaker_statistics_in_transcript(tmp_path):
    """Test speaker statistics calculation in full transcript."""
    result = _make_basic_result()
    result.duration = 100.0
    result.utterances = [
        TranscriptionUtterance(
            speaker=0, start=0.0, end=40.0, text="Speaker 1 talks for 40 seconds."
        ),
        TranscriptionUtterance(
            speaker=1, start=40.0, end=60.0, text="Speaker 2 talks for 20 seconds."
        ),
        TranscriptionUtterance(
            speaker=0, start=60.0, end=100.0, text="Speaker 1 talks for another 40."
        ),
    ]

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "speakers")

    transcript_md = (tmp_path / "04_full_transcript_with_timestamps.md").read_text(encoding="utf-8")

    # Verify speaker statistics section exists
    assert "Speaker Statistics" in transcript_md
    assert "Speaker 1:" in transcript_md  # 0-indexed speaker displayed as 1
    assert "Speaker 2:" in transcript_md


def test_output_directory_creation(tmp_path):
    """Test that output directory is created if it doesn't exist."""
    result = _make_basic_result()
    nested_dir = tmp_path / "nested" / "output"

    # Directory should not exist yet
    assert not nested_dir.exists()

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, nested_dir, "test")

    # Directory should be created
    assert nested_dir.exists()
    assert (nested_dir / "01_executive_summary.md").exists()


def test_topics_sorting_by_frequency(tmp_path):
    """Test that topics are sorted by frequency in descending order."""
    result = _make_basic_result()
    result.topics = {"planning": 3, "execution": 5, "review": 1}

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "topics")

    topics_md = (tmp_path / "03_key_topics_and_intents.md").read_text(encoding="utf-8")

    # execution (5) should appear before planning (3) before review (1)
    exec_pos = topics_md.index("execution")
    plan_pos = topics_md.index("planning")
    review_pos = topics_md.index("review")

    assert exec_pos < plan_pos < review_pos


def test_insights_with_timestamps(tmp_path):
    """Test that insights include timestamps when utterances available."""
    result = _make_basic_result()
    result.transcript = "We should implement the new feature. The team will review it."
    result.utterances = [
        TranscriptionUtterance(
            speaker=0, start=10.0, end=15.0, text="We should implement the new feature."
        ),
        TranscriptionUtterance(speaker=1, start=20.0, end=25.0, text="The team will review it."),
    ]

    analyzer = FullAnalyzer()
    analyzer.analyze_and_save(result, tmp_path, "insights")

    insights_md = (tmp_path / "05_key_insights_and_takeaways.md").read_text(encoding="utf-8")

    # Should include timestamp markers
    assert "Timestamp" in insights_md
    assert "00:00:10" in insights_md or "Evidence" in insights_md
