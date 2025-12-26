"""ElevenLabs API client wrapper.

This module provides a wrapper around the ElevenLabs SDK with
standardized retry, timeout, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base_client import BaseAPIClient

if TYPE_CHECKING:
    pass


class ElevenLabsAPIClient(BaseAPIClient):
    """Wrapper for ElevenLabs SDK client.

    This class wraps the ElevenLabs SDK to provide:
    - Consistent retry logic
    - Standardized error handling
    - Timeout management
    """

    def _create_sdk_client(self) -> object:
        """Create ElevenLabs SDK client.

        Returns:
            ElevenLabsClient instance
        """
        from elevenlabs.client import ElevenLabs as ElevenLabsClient

        return ElevenLabsClient(api_key=self.api_key)

    async def transcribe_file(
        self,
        audio_file: Path,
        options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio file using ElevenLabs API.

        Args:
            audio_file: Path to audio file
            options: ElevenLabs API options (model, language, etc.)
            timeout: Override default timeout in seconds

        Returns:
            Transcription result dictionary

        Raises:
            ProviderAPIError: If transcription fails
        """
        client = self._get_sdk_client()
        effective_timeout = timeout if timeout is not None else self._default_timeout

        async def _transcribe() -> dict[str, Any]:
            return await self._transcribe_with_client(client, audio_file, options, effective_timeout)

        return await self._execute_with_retry(_transcribe)

    async def _transcribe_with_client(
        self,
        client: object,
        audio_file: Path,
        options: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        """Execute transcription with ElevenLabs client.

        Args:
            client: ElevenLabsClient instance
            audio_file: Audio file to transcribe
            options: API options

        Returns:
            Transcription result
        """
        import asyncio

        with open(audio_file, "rb") as f:
            audio_bytes = f.read()

        async def _convert() -> dict[str, Any]:
            return await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.speech_to_text.convert(
                    file=audio_bytes,
                    **(options or {}),
                ),
            )

        from src.utils.retry import retry_async

        @retry_async(config=self._retry_config)
        async def _wrapped_convert() -> dict[str, Any]:
            try:
                return await asyncio.wait_for(
                    _convert(),
                    timeout=int(timeout),
                )
            except TimeoutError:
                from ..exceptions import ProviderAPIError

                raise ProviderAPIError(f"ElevenLabs transcription timed out after {timeout}s")

        return await _wrapped_convert()

    async def health_check(self) -> dict[str, Any]:
        """Check ElevenLabs API health status.

        Returns:
            Health status dictionary
        """
        client = self._get_sdk_client()

        async def _check() -> dict[str, Any]:
            try:
                import asyncio

                user_info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.user.get_user_info(),
                )
                return {"status": "healthy", "user": user_info.get("username", "unknown")}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}

        return await self._execute_with_retry(
            _check,
            context={"operation": "health_check", "provider": "elevenlabs"},
        )


__all__ = ["ElevenLabsAPIClient"]
