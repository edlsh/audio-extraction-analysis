from __future__ import annotations

from typing import Any, Protocol


class _Segment(Protocol):
    start: float
    end: float
    text: str


class _SpeechToTextResult(Protocol):
    text: str | None
    transcript: str | None
    segments: list[_Segment] | None


class _SpeechToText(Protocol):
    def convert(
        self,
        *,
        file: bytes,
        model_id: str,
        language_code: str | None = ...,  # optional language
        **kwargs: Any,
    ) -> _SpeechToTextResult: ...


class _User(Protocol):
    def get_user_info(self) -> Any: ...


class ElevenLabs:
    def __init__(self, api_key: str | None = ...) -> None: ...
    user: _User
    speech_to_text: _SpeechToText


class ClientUser(_User):
    def get_user_info(self) -> Any: ...


class ClientSpeechToText(_SpeechToText):
    def convert(
        self,
        *,
        file: bytes,
        model_id: str,
        language_code: str | None = ...,  # optional language
        **kwargs: Any,
    ) -> _SpeechToTextResult: ...


class ElevenLabsClient:
    def __init__(self, *, api_key: str | None = ...) -> None: ...
    user: ClientUser
    speech_to_text: ClientSpeechToText


__all__ = [
    "ElevenLabs",
    "ElevenLabsClient",
    "ClientUser",
    "ClientSpeechToText",
]
