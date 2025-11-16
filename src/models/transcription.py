"""Data models for transcription results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TranscriptionSpeaker:
    """Information about a speaker in the transcription."""

    id: int
    total_time: float
    percentage: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "total_time": self.total_time,
            "percentage": self.percentage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptionSpeaker:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            total_time=data["total_time"],
            percentage=data["percentage"],
        )


@dataclass
class TranscriptionChapter:
    """A chapter/topic segment in the transcription."""

    start_time: float
    end_time: float
    topics: list[str]
    confidence_scores: list[float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "topics": self.topics,
            "confidence_scores": self.confidence_scores,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptionChapter:
        """Create from dictionary."""
        return cls(
            start_time=data["start_time"],
            end_time=data["end_time"],
            topics=data["topics"],
            confidence_scores=data["confidence_scores"],
        )


@dataclass
class TranscriptionUtterance:
    """A single utterance in the transcription."""

    speaker: int
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "speaker": self.speaker,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptionUtterance:
        """Create from dictionary."""
        return cls(
            speaker=data["speaker"],
            start=data["start"],
            end=data["end"],
            text=data["text"],
        )


@dataclass
class TranscriptionResult:
    """Complete transcription result with all features."""

    # Basic transcription
    transcript: str

    # Metadata
    duration: float
    generated_at: datetime
    audio_file: str

    # Provider information
    provider_name: str = "unknown"
    provider_features: list[str] | None = None

    # Advanced features
    summary: str | None = None
    chapters: list[TranscriptionChapter] | None = None
    speakers: list[TranscriptionSpeaker] | None = None
    utterances: list[TranscriptionUtterance] | None = None
    topics: dict[str, int] | None = None
    intents: list[str] | None = None
    sentiment_distribution: dict[str, int] | None = None

    # Generic metadata storage
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize empty collections if None."""
        if self.provider_features is None:
            self.provider_features = []
        if self.chapters is None:
            self.chapters = []
        if self.speakers is None:
            self.speakers = []
        if self.utterances is None:
            self.utterances = []
        if self.topics is None:
            self.topics = {}
        if self.intents is None:
            self.intents = []
        if self.sentiment_distribution is None:
            self.sentiment_distribution = {}
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "transcript": self.transcript,
            "duration": self.duration,
            "generated_at": self.generated_at.isoformat(),
            "audio_file": self.audio_file,
            "provider_name": self.provider_name,
            "provider_features": self.provider_features,
            "summary": self.summary,
            "chapters": [chapter.to_dict() for chapter in self.chapters] if self.chapters else [],
            "speakers": [speaker.to_dict() for speaker in self.speakers] if self.speakers else [],
            "utterances": (
                [utterance.to_dict() for utterance in self.utterances] if self.utterances else []
            ),
            "topics": self.topics,
            "intents": self.intents,
            "sentiment_distribution": self.sentiment_distribution,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptionResult:
        """Create from dictionary."""
        return cls(
            transcript=data["transcript"],
            duration=data["duration"],
            generated_at=datetime.fromisoformat(data["generated_at"]),
            audio_file=data["audio_file"],
            provider_name=data.get("provider_name", "unknown"),
            provider_features=data.get("provider_features"),
            summary=data.get("summary"),
            chapters=(
                [
                    TranscriptionChapter.from_dict(chapter_data)
                    for chapter_data in data.get("chapters", [])
                ]
                if data.get("chapters")
                else None
            ),
            speakers=(
                [
                    TranscriptionSpeaker.from_dict(speaker_data)
                    for speaker_data in data.get("speakers", [])
                ]
                if data.get("speakers")
                else None
            ),
            utterances=(
                [
                    TranscriptionUtterance.from_dict(utterance_data)
                    for utterance_data in data.get("utterances", [])
                ]
                if data.get("utterances")
                else None
            ),
            topics=data.get("topics"),
            intents=data.get("intents"),
            sentiment_distribution=data.get("sentiment_distribution"),
            metadata=data.get("metadata"),
        )
