"""
Type stubs for deepgram-sdk library.

This stub file provides type annotations for the Deepgram SDK,
which has partial type information.
"""

from typing import Any, Protocol, TypedDict
from pathlib import Path


class DeepgramClient(Protocol):
    """Deepgram client protocol."""

    @property
    def listen(self) -> ListenClient: ...


class ListenClient(Protocol):
    """Listen client for transcription."""

    @property
    def prerecorded(self) -> PrerecordedClient: ...

    @property
    def asyncprerecorded(self) -> AsyncPrerecordedClient: ...


class PrerecordedClient(Protocol):
    """Synchronous prerecorded transcription client."""

    def v(self, version: str) -> PrerecordedVersionedClient: ...


class AsyncPrerecordedClient(Protocol):
    """Asynchronous prerecorded transcription client."""

    def v(self, version: str) -> AsyncPrerecordedVersionedClient: ...


class PrerecordedVersionedClient(Protocol):
    """Versioned prerecorded client."""

    def transcribe_file(
        self,
        source: dict[str, Any],
        options: PrerecordedOptions,
    ) -> PrerecordedResponse: ...


class AsyncPrerecordedVersionedClient(Protocol):
    """Async versioned prerecorded client."""

    async def transcribe_file(
        self,
        source: dict[str, Any],
        options: PrerecordedOptions,
    ) -> PrerecordedResponse: ...


class PrerecordedOptions:
    """Options for prerecorded transcription."""

    def __init__(
        self,
        *,
        language: str = "en",
        model: str = "nova-2",
        smart_format: bool = False,
        punctuate: bool = True,
        paragraphs: bool = False,
        utterances: bool = False,
        diarize: bool = False,
        multichannel: bool = False,
        alternatives: int = 1,
        numerals: bool = False,
        search: list[str] | None = None,
        replace: list[str] | None = None,
        keywords: list[str] | None = None,
        profanity_filter: bool = False,
        redact: list[str] | None = None,
        ner: bool = False,
        **kwargs: Any,
    ) -> None: ...


class PrerecordedResponse:
    """Response from prerecorded transcription."""

    results: Results
    metadata: Metadata


class Results:
    """Transcription results."""

    channels: list[Channel]


class Channel:
    """Audio channel results."""

    alternatives: list[Alternative]


class Alternative:
    """Transcription alternative."""

    transcript: str
    confidence: float
    words: list[Word] | None
    paragraphs: Paragraphs | None


class Word:
    """Individual word timing."""

    word: str
    start: float
    end: float
    confidence: float
    speaker: int | None
    punctuated_word: str | None


class Paragraphs:
    """Paragraph grouping of transcript."""

    transcript: str
    paragraphs: list[Paragraph]


class Paragraph:
    """Individual paragraph."""

    sentences: list[Sentence]
    start: float
    end: float
    num_words: int


class Sentence:
    """Individual sentence."""

    text: str
    start: float
    end: float


class Metadata:
    """Transcription metadata."""

    request_id: str
    model_info: ModelInfo
    sha256: str
    created: str
    duration: float
    channels: int


class ModelInfo:
    """Model information."""

    name: str
    version: str
    arch: str


class ClientOptions:
    """Client configuration options."""

    api_key: str
    url: str | None
    headers: dict[str, str] | None

    def __init__(
        self,
        api_key: str,
        url: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...


class ClientOptionsFromEnv:
    """Client options loaded from environment variables.
    
    Reads DEEPGRAM_API_KEY and other configuration from environment.
    """

    def __init__(self, *, options: dict[str, Any] | None = None) -> None:
        """Initialize client options from environment.
        
        Args:
            options: Optional dictionary of additional options (e.g., timeout)
        """
        ...
