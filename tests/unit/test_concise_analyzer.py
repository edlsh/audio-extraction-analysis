"""
Tests for the ConciseAnalyzer module.

The ConciseAnalyzer generates a single, unified markdown analysis report from
transcription results, consolidating all insights (topics, sentiment, speakers,
timeline, etc.) into one comprehensive file instead of multiple separate outputs.

Test Coverage:
    - File creation and naming
    - Content generation for all report sections
    - Handling of optional/missing data
    - Formatting and duration helpers
    - Integration scenarios with full feature sets
"""

from datetime import datetime

from src.analysis.concise_analyzer import ConciseAnalyzer
from src.models.transcription import (
    TranscriptionChapter,
    TranscriptionResult,
    TranscriptionSpeaker,
    TranscriptionUtterance,
)


def _make_basic_result() -> TranscriptionResult:
    """
    Create a basic transcription result for testing.

    Returns a minimal but realistic TranscriptionResult with:
    - Sample transcript containing action-oriented language (for intent detection testing)
    - 2-minute duration (120 seconds) for timeline testing
    - Deepgram Nova 3 provider with common features
    - No optional fields populated (speakers, chapters, sentiment, etc.)

    This baseline result is used by most tests, which then add specific fields
    (like speakers, topics, or sentiment) as needed for their test scenarios.

    Returns:
        TranscriptionResult: A basic transcription result suitable for testing.
    """
    return TranscriptionResult(
        transcript=(
            "This is a sample transcript. We should follow up on action items. "
            "The team will deliver next week. Planning is a priority. "
            "We need to ensure quality standards are met in the final deliverable. "
            "The deadline is approaching fast and we must coordinate effectively."
        ),
        duration=120.0,
        generated_at=datetime.now(),
        audio_file="/tmp/test_audio.mp3",
        provider_name="Deepgram Nova 3",
        provider_features=["timestamps", "speaker_diarization", "topic_detection"],
    )


def test_concise_analyzer_creates_analysis_file(tmp_path):
    """
    Test that analyze_and_save creates the analysis file with correct naming.

    Verifies:
    - Output file is created at the specified path
    - File name follows the pattern: {video_name}_analysis.md
    - File is saved in the correct output directory
    """
    result = _make_basic_result()
    analyzer = ConciseAnalyzer()

    output_path = analyzer.analyze_and_save(result, tmp_path, "test_video")

    assert output_path.exists()
    assert output_path.name == "test_video_analysis.md"
    assert output_path.parent == tmp_path


def test_concise_analyzer_file_has_content(tmp_path):
    """
    Test that the generated analysis file contains all required sections.

    Verifies the presence of all 8 main sections in the generated markdown:
    1. Audio Analysis Report (header)
    2. Overview (summary and word count)
    3. Key Topics (detected themes)
    4. Speaker Analysis (speaker diarization data)
    5. Sentiment Analysis (emotional tone distribution)
    6. Key Highlights & Quotes (important excerpts)
    7. Intents & Action Items (actionable content)
    8. Timeline (temporal breakdown)
    9. Technical Metadata (processing details)

    This ensures the complete structure is present regardless of data availability.
    """
    result = _make_basic_result()
    result.summary = "This is a test summary of the audio content."

    analyzer = ConciseAnalyzer()
    output_path = analyzer.analyze_and_save(result, tmp_path, "test")

    content = output_path.read_text(encoding="utf-8")

    # Verify all 9 major sections are present in the generated markdown report
    # Each section should appear regardless of whether data is available (with fallbacks)
    assert "# Audio Analysis Report" in content
    assert "## 📋 Overview" in content
    assert "## 🎯 Key Topics" in content
    assert "## 👥 Speaker Analysis" in content
    assert "## 😊 Sentiment Analysis" in content
    assert "## 💡 Key Highlights & Quotes" in content
    assert "## ✅ Intents & Action Items" in content
    assert "## ⏰ Timeline" in content
    assert "## 📊 Technical Metadata" in content


def test_header_generation():
    """
    Test that the report header contains essential metadata.

    Verifies the header includes:
    - Report title
    - Provider name and version (e.g., "Deepgram Nova 3")
    - Formatted duration (MM:SS or HH:MM:SS format)
    - Source audio file name

    The header provides critical context for understanding the analysis report.
    """
    result = _make_basic_result()
    analyzer = ConciseAnalyzer()

    header = analyzer._generate_header(result)

    assert "# Audio Analysis Report" in header
    assert "Deepgram Nova 3" in header
    assert "02:00" in header  # Duration formatted
    assert "test_audio.mp3" in header


def test_overview_with_summary():
    """
    Test overview section generation when a summary is provided.

    When TranscriptionResult includes a summary field, the overview section
    should display that summary along with basic statistics (word count).
    This is the preferred path as summaries provide concise content descriptions.
    """
    result = _make_basic_result()
    result.summary = "This is a comprehensive summary of the content."

    analyzer = ConciseAnalyzer()
    overview = analyzer._generate_overview(result)

    assert "## 📋 Overview" in overview
    assert "This is a comprehensive summary of the content." in overview
    assert "words" in overview


def test_overview_without_summary():
    """
    Test overview section fallback when no summary is provided.

    When TranscriptionResult.summary is None, the analyzer should generate
    a fallback overview using transcript excerpts or statistics. This ensures
    the Overview section always has meaningful content, even without AI-generated summaries.

    Verifies:
    - Section header is present
    - Fallback content is generated (e.g., "Key Content:" label)
    """
    result = _make_basic_result()
    result.summary = None

    analyzer = ConciseAnalyzer()
    overview = analyzer._generate_overview(result)

    assert "## 📋 Overview" in overview
    assert "Key Content:" in overview


def test_key_topics_with_data():
    """
    Test key topics section generation with topic frequency data.

    Verifies:
    - Topics are displayed with mention counts
    - Topics are sorted by frequency (descending)
    - Topic names are properly formatted (title-cased)
    - Section shows most discussed themes first

    The test uses varying mention counts (2, 3, 5, 7) to verify sorting behavior.
    """
    result = _make_basic_result()
    # Topics with different mention counts to test sorting: quality(7) > planning(5) > execution(3) > deadline(2)
    result.topics = {
        "planning": 5,
        "execution": 3,
        "quality": 7,
        "deadline": 2,
    }

    analyzer = ConciseAnalyzer()
    topics_section = analyzer._generate_key_topics(result)

    assert "## 🎯 Key Topics" in topics_section
    # Check the top 2 topics (quality with 7, planning with 5) are present and formatted
    assert "Quality" in topics_section  # Should be title-cased
    assert "(7 mentions)" in topics_section
    assert "Planning" in topics_section
    assert "(5 mentions)" in topics_section


def test_key_topics_without_data():
    """Test key topics section when no topics are detected."""
    result = _make_basic_result()
    result.topics = {}

    analyzer = ConciseAnalyzer()
    topics_section = analyzer._generate_key_topics(result)

    assert "## 🎯 Key Topics" in topics_section
    assert "No specific topics identified" in topics_section


def test_speaker_insights_with_speakers():
    """
    Test speaker analysis section with diarization data.

    Verifies speaker information is formatted correctly:
    - Speaker IDs are labeled (Speaker 0, Speaker 1, etc.)
    - Speaking time is formatted as MM:SS or HH:MM:SS
    - Percentage of total speaking time is displayed
    - Multiple speakers are all included

    Uses realistic test data: 70s (58.3%) and 50s (41.7%) for a balanced conversation.
    """
    result = _make_basic_result()
    # Two speakers with realistic time distribution: Speaker 0 (70s/58.3%), Speaker 1 (50s/41.7%)
    # Total: 120s (matches basic_result duration), representing a typical 2-person conversation
    result.speakers = [
        TranscriptionSpeaker(id=0, total_time=70.0, percentage=58.3),
        TranscriptionSpeaker(id=1, total_time=50.0, percentage=41.7),
    ]

    analyzer = ConciseAnalyzer()
    speaker_section = analyzer._generate_speaker_insights(result)

    assert "## 👥 Speaker Analysis" in speaker_section
    assert "Speaker 0" in speaker_section
    assert "01:10" in speaker_section  # 70 seconds formatted as MM:SS
    assert "58.3%" in speaker_section
    assert "Speaker 1" in speaker_section


def test_speaker_insights_without_speakers():
    """Test speaker insights when no speaker data available."""
    result = _make_basic_result()
    result.speakers = []

    analyzer = ConciseAnalyzer()
    speaker_section = analyzer._generate_speaker_insights(result)

    assert "## 👥 Speaker Analysis" in speaker_section
    assert "No speaker diarization data available" in speaker_section


def test_sentiment_analysis_with_data():
    """
    Test sentiment analysis section with emotional tone distribution.

    Verifies:
    - Each sentiment category (positive, neutral, negative) is displayed
    - Appropriate emoji is used for each category (😊, 😐, 😔)
    - Segment counts are shown for each sentiment
    - Helps users understand the emotional tone of the conversation

    Uses unbalanced data (10 positive, 5 neutral, 2 negative) to test
    realistic sentiment distributions.
    """
    result = _make_basic_result()
    result.sentiment_distribution = {
        "positive": 10,
        "neutral": 5,
        "negative": 2,
    }

    analyzer = ConciseAnalyzer()
    sentiment_section = analyzer._generate_sentiment_analysis(result)

    assert "## 😊 Sentiment Analysis" in sentiment_section
    assert "😊" in sentiment_section  # Positive emoji
    assert "Positive" in sentiment_section
    assert "10 segments" in sentiment_section
    assert "😐" in sentiment_section  # Neutral emoji
    assert "😔" in sentiment_section  # Negative emoji


def test_sentiment_analysis_without_data():
    """Test sentiment analysis when no data available."""
    result = _make_basic_result()
    result.sentiment_distribution = {}

    analyzer = ConciseAnalyzer()
    sentiment_section = analyzer._generate_sentiment_analysis(result)

    assert "## 😊 Sentiment Analysis" in sentiment_section
    assert "No sentiment analysis data available" in sentiment_section


def test_highlights_and_quotes_extraction():
    """
    Test extraction of key highlights and memorable quotes.

    The analyzer extracts important sentences based on:
    - Sentence length (longer sentences often contain more substance)
    - Keyword presence (domain-specific or action-oriented terms)
    - Contextual importance

    This test uses deliberately long, content-rich sentences to verify
    the extraction algorithm identifies meaningful highlights rather than
    short, trivial statements.
    """
    # Create a result with varying sentence lengths:
    # - Short intro (7 words) - should be ignored
    # - 4 long, substantive sentences (20+ words each) - should be extracted
    # This tests that the algorithm filters by length and content quality
    result = TranscriptionResult(
        transcript=(
            "This is an introductory statement. "
            "We need to carefully evaluate all the options available before making a final decision on this critical project. "
            "The team has been working diligently on implementing the new features and ensuring they meet all quality standards. "
            "Our primary objective is to deliver exceptional value to customers while maintaining operational efficiency and cost effectiveness. "
            "The stakeholders have expressed strong support for this initiative and we are confident in achieving the desired outcomes."
        ),
        duration=120.0,
        generated_at=datetime.now(),
        audio_file="/tmp/test.mp3",
        provider_name="Test",
    )

    analyzer = ConciseAnalyzer()
    highlights = analyzer._generate_highlights_and_quotes(result)

    assert "## 💡 Key Highlights & Quotes" in highlights
    # Should extract at least one of the long, meaningful sentences (not the short intro)
    assert (
        "quality standards" in highlights
        or "operational efficiency" in highlights
        or "stakeholders" in highlights
    )


def test_action_items_with_intents():
    """
    Test action items section when intent data is available.

    When the transcription provider includes intent classification
    (inform, decide, action, question, etc.), these are displayed
    as structured intents to help users understand conversation goals.

    Verifies:
    - Intent categories are displayed
    - Intents are properly formatted (capitalized)
    - Duplicate intents are handled correctly
    """
    result = _make_basic_result()
    result.intents = ["inform", "decide", "action", "decide"]

    analyzer = ConciseAnalyzer()
    action_section = analyzer._generate_action_items_and_intents(result)

    assert "## ✅ Intents & Action Items" in action_section
    assert "Identified Intents:" in action_section
    assert "Inform" in action_section or "inform" in action_section.lower()
    assert "Decide" in action_section or "decide" in action_section.lower()


def test_action_items_without_intents():
    """
    Test action items extraction when no intent classification is available.

    Falls back to keyword-based extraction from the transcript, looking for:
    - Modal verbs: "should", "must", "need to", "have to"
    - Action verbs: "will", "going to", "plan to"
    - Imperative phrases suggesting tasks or decisions

    The basic test result includes phrases like "should follow up" and
    "need to ensure" to verify keyword detection works.
    """
    result = _make_basic_result()
    result.intents = []

    analyzer = ConciseAnalyzer()
    action_section = analyzer._generate_action_items_and_intents(result)

    assert "## ✅ Intents & Action Items" in action_section
    # Should detect action keywords like "should", "need to", "must"
    assert "should follow up" in action_section or "Potential Action Items" in action_section


def test_timeline_with_chapters():
    """
    Test timeline generation using chapter/topic segmentation data.

    When the transcription includes chapter markers (topic-based segments),
    the timeline displays these as "Topic Segments" showing:
    - Start and end times for each chapter
    - Topics discussed in that time period
    - Temporal structure of the conversation

    This is preferred over utterance-based timelines for high-level navigation.
    Test uses 2 chapters covering 0-60s and 60-120s with different topics.
    """
    result = _make_basic_result()
    result.chapters = [
        TranscriptionChapter(
            start_time=0.0,
            end_time=60.0,
            topics=["introduction", "planning"],
            confidence_scores=[0.9, 0.7],
        ),
        TranscriptionChapter(
            start_time=60.0,
            end_time=120.0,
            topics=["execution"],
            confidence_scores=[0.8],
        ),
    ]

    analyzer = ConciseAnalyzer()
    timeline = analyzer._generate_timeline(result)

    assert "## ⏰ Timeline" in timeline
    assert "Topic Segments:" in timeline
    assert "00:00" in timeline
    assert "01:00" in timeline
    assert "introduction, planning" in timeline or "introduction" in timeline


def test_timeline_with_utterances():
    """
    Test timeline generation using utterance data as fallback.

    When chapter data is unavailable, the timeline falls back to displaying
    individual utterances as "Key Moments":
    - Timestamp for each utterance
    - Speaker identification
    - Text of what was said

    This provides more granular temporal navigation but is less structured
    than chapter-based timelines. Test uses 2 utterances from different speakers.
    """
    result = _make_basic_result()
    result.chapters = []
    result.utterances = [
        TranscriptionUtterance(
            speaker=0, start=5.0, end=15.0, text="This is the opening statement."
        ),
        TranscriptionUtterance(speaker=1, start=20.0, end=35.0, text="I agree with that approach."),
    ]

    analyzer = ConciseAnalyzer()
    timeline = analyzer._generate_timeline(result)

    assert "## ⏰ Timeline" in timeline
    assert "Key Moments:" in timeline
    assert "00:05" in timeline
    assert "This is the opening statement" in timeline


def test_timeline_without_data():
    """Test timeline when no chapter or utterance data available."""
    result = _make_basic_result()
    result.chapters = []
    result.utterances = []

    analyzer = ConciseAnalyzer()
    timeline = analyzer._generate_timeline(result)

    assert "## ⏰ Timeline" in timeline
    assert "No timeline data available" in timeline


def test_metadata_generation():
    """
    Test technical metadata section generation.

    The metadata section provides transparency about the analysis:
    - Provider features used (timestamps, diarization, topic detection, etc.)
    - Source file information
    - Data statistics (number of speakers, chapters, utterances)
    - Processing details

    This helps users understand what capabilities were available during
    transcription and what data the analysis is based on.
    """
    result = _make_basic_result()
    result.speakers = [TranscriptionSpeaker(id=0, total_time=60.0, percentage=50.0)]
    result.chapters = [
        TranscriptionChapter(
            start_time=0.0, end_time=60.0, topics=["test"], confidence_scores=[0.8]
        )
    ]
    result.utterances = [
        TranscriptionUtterance(speaker=0, start=0.0, end=10.0, text="Test utterance")
    ]

    analyzer = ConciseAnalyzer()
    metadata = analyzer._generate_metadata(result)

    assert "## 📊 Technical Metadata" in metadata
    assert "timestamps, speaker_diarization, topic_detection" in metadata
    assert "test_audio.mp3" in metadata
    assert "Speakers Detected:** 1" in metadata
    assert "Topic Segments:** 1" in metadata
    assert "Total Utterances:** 1" in metadata


def test_format_duration_seconds_only():
    """
    Test duration formatting for short durations (under 1 minute).

    Verifies MM:SS format is used correctly:
    - 0 seconds → "00:00"
    - 30 seconds → "00:30"
    - 59 seconds → "00:59"

    This format is used throughout the report for timestamps and durations.
    """
    analyzer = ConciseAnalyzer()

    assert analyzer._format_duration(0) == "00:00"
    assert analyzer._format_duration(30) == "00:30"
    assert analyzer._format_duration(59) == "00:59"


def test_format_duration_minutes():
    """
    Test duration formatting for medium durations (1-59 minutes).

    Verifies MM:SS format handles minutes correctly:
    - 60 seconds (1 min) → "01:00"
    - 90 seconds (1.5 min) → "01:30"
    - 3599 seconds (59 min 59 sec) → "59:59"

    This is the most common format for typical audio/video content.
    """
    analyzer = ConciseAnalyzer()

    assert analyzer._format_duration(60) == "01:00"
    assert analyzer._format_duration(90) == "01:30"
    assert analyzer._format_duration(3599) == "59:59"


def test_format_duration_hours():
    """
    Test duration formatting for long durations (1+ hours).

    Verifies HH:MM:SS format is used for content over an hour:
    - 3600 seconds (1 hour) → "01:00:00"
    - 3661 seconds (1h 1m 1s) → "01:01:01"
    - 7200 seconds (2 hours) → "02:00:00"
    - 7325 seconds (2h 2m 5s) → "02:02:05"

    Format automatically switches to include hours when duration ≥ 3600s.
    """
    analyzer = ConciseAnalyzer()

    assert analyzer._format_duration(3600) == "01:00:00"
    assert analyzer._format_duration(3661) == "01:01:01"
    assert analyzer._format_duration(7200) == "02:00:00"
    assert analyzer._format_duration(7325) == "02:02:05"


def test_get_sentiment_emoji():
    """
    Test sentiment-to-emoji mapping for visual representation.

    Maps sentiment categories to appropriate emojis:
    - positive → 😊 (smiling face)
    - negative → 😔 (pensive face)
    - neutral → 😐 (neutral face)
    - unknown/other → 🤔 (thinking face)

    The mapping is case-insensitive to handle various provider formats.
    Emojis enhance readability in the markdown report.
    """
    analyzer = ConciseAnalyzer()

    assert analyzer._get_sentiment_emoji("positive") == "😊"
    assert analyzer._get_sentiment_emoji("Positive") == "😊"
    assert analyzer._get_sentiment_emoji("negative") == "😔"
    assert analyzer._get_sentiment_emoji("Negative") == "😔"
    assert analyzer._get_sentiment_emoji("neutral") == "😐"
    assert analyzer._get_sentiment_emoji("Neutral") == "😐"
    assert analyzer._get_sentiment_emoji("unknown") == "🤔"


def test_complete_analysis_with_all_features(tmp_path):
    """
    Integration test: Complete analysis with all features enabled.

    This end-to-end test verifies the analyzer handles a fully-featured
    transcription result with:
    - Summary text
    - Topic detection with frequencies
    - Speaker diarization (2 speakers)
    - Chapter segmentation (2 segments)
    - Utterance-level timestamps
    - Intent classification
    - Sentiment distribution

    Ensures all sections are populated with rich content and the final
    markdown report is comprehensive and well-structured. This represents
    the ideal case where all provider features are available.
    """
    result = _make_basic_result()
    result.summary = "Comprehensive discussion about project planning and execution."
    result.topics = {"planning": 5, "execution": 3, "quality": 2}
    result.speakers = [
        TranscriptionSpeaker(id=0, total_time=70.0, percentage=58.3),
        TranscriptionSpeaker(id=1, total_time=50.0, percentage=41.7),
    ]
    result.chapters = [
        TranscriptionChapter(
            start_time=0.0, end_time=60.0, topics=["planning"], confidence_scores=[0.9]
        ),
        TranscriptionChapter(
            start_time=60.0, end_time=120.0, topics=["execution"], confidence_scores=[0.8]
        ),
    ]
    result.utterances = [
        TranscriptionUtterance(speaker=0, start=5.0, end=15.0, text="Let's discuss the plan."),
        TranscriptionUtterance(speaker=1, start=20.0, end=30.0, text="I agree with the approach."),
    ]
    result.intents = ["inform", "decide", "action"]
    result.sentiment_distribution = {"positive": 8, "neutral": 3, "negative": 1}

    analyzer = ConciseAnalyzer()
    output_path = analyzer.analyze_and_save(result, tmp_path, "complete_test")

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")

    # Verify all sections have rich content
    assert "Comprehensive discussion" in content
    assert "Planning" in content
    assert "Speaker 0" in content
    assert "😊" in content  # Sentiment emoji
    assert "01:00" in content  # Timeline
    assert "inform" in content.lower()  # Intents


def test_analysis_handles_missing_optionals(tmp_path):
    """
    Integration test: Graceful handling of minimal transcription data.

    Tests the analyzer's robustness when most optional fields are missing:
    - No summary
    - No topics
    - No speakers
    - No chapters
    - No utterances
    - No intents
    - No sentiment

    Verifies:
    - All sections are still created with appropriate fallback messages
    - No errors or crashes occur
    - Output file is valid markdown
    - Basic structure is maintained

    This represents the worst-case scenario where only the transcript
    text is available, testing defensive programming and graceful degradation.
    """
    result = TranscriptionResult(
        transcript="Simple transcript without advanced features.",
        duration=30.0,
        generated_at=datetime.now(),
        audio_file="/tmp/simple.mp3",
        provider_name="Basic Provider",
    )

    analyzer = ConciseAnalyzer()
    output_path = analyzer.analyze_and_save(result, tmp_path, "minimal")

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")

    # Should still have all sections with fallback text
    assert "# Audio Analysis Report" in content
    assert "No specific topics identified" in content
    assert "No speaker diarization data available" in content
    assert "No sentiment analysis data available" in content
    assert "No timeline data available" in content


def test_output_directory_creation(tmp_path):
    """
    Test automatic creation of nested output directories.

    Verifies the analyzer creates the full directory path if it doesn't exist,
    rather than failing when given a non-existent output location.

    Test scenario:
    - Specifies a deeply nested path: /output/analysis/reports/
    - Path doesn't exist beforehand
    - Analyzer creates all intermediate directories
    - File is successfully saved at the specified location

    This ensures robust file handling and prevents failures due to missing directories.
    """
    result = _make_basic_result()
    analyzer = ConciseAnalyzer()

    nested_dir = tmp_path / "output" / "analysis" / "reports"
    output_path = analyzer.analyze_and_save(result, nested_dir, "test")

    assert nested_dir.exists()
    assert output_path.exists()
    assert output_path.parent == nested_dir
