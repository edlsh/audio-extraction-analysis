"""Deepgram API client wrapper.

This module provides a wrapper around the Deepgram SDK with
standardized retry, timeout, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from .base_client import BaseAPIClient


class DeepgramAPIClient(BaseAPIClient):
    """Wrapper for Deepgram SDK client.

    This class wraps the Deepgram SDK to provide:
    - Consistent retry logic
    - Standardized error handling
    - Timeout management
    """

    def _create_sdk_client(self) -> object:
        """Create Deepgram SDK client.

        Returns:
            DeepgramClient instance
        """
        from deepgram import DeepgramClient

        return DeepgramClient(api_key=self.api_key)

    async def transcribe_file(
        self,
        audio_file: Path | BinaryIO,
        options: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio file using Deepgram API.

        Args:
            audio_file: Path to audio file or BinaryIO object
            options: Deepgram API options (model, language, etc.)
            timeout: Override default timeout in seconds

        Returns:
            Transcription result dictionary

        Raises:
            ProviderAPIError: If transcription fails
        """
        client = self._get_sdk_client()
        timeout_val = timeout if timeout is not None else self._default_timeout

        async def _transcribe() -> dict[str, Any]:
            return await self._transcribe_with_client(client, audio_file, options, timeout_val)

        return await self._execute_with_retry(
            _transcribe,
            context={"operation": "transcribe_file", "provider": "deepgram"},
        )

    async def _transcribe_with_client(
        self,
        client: object,
        audio_file: Path | BinaryIO,
        options: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Execute transcription with Deepgram client.

        Args:
            client: DeepgramClient instance
            audio_file: Audio file to transcribe
            options: API options
            timeout: Timeout in seconds

        Returns:
            Transcription result
        """
        import asyncio

        # Use streaming upload for large files (> 100MB)
        from src.utils.file_size import get_file_size_bytes

        if isinstance(audio_file, Path):
            file_size = get_file_size_bytes(audio_file)
            if file_size > 100 * 1024 * 1024:  # 100MB
                return await self._streaming_transcribe(client, audio_file, options, timeout)

        # Small file - direct upload (run in executor since SDK is sync)
        return await asyncio.to_thread(
            client.listen.v1.media.transcribe_file,
            request=audio_file,
            options=options,
            request_options={"timeout_in_seconds": int(timeout)},
        )

    async def _streaming_transcribe(
        self,
        client: object,
        audio_file: Path,
        options: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Execute streaming transcription for large files.

        Args:
            client: DeepgramClient instance
            audio_file: Audio file to transcribe
            options: API options
            timeout: Timeout in seconds

        Returns:
            Transcription result
        """
        import asyncio

        # Pass the file path directly - SDK handles streaming efficiently
        return await asyncio.to_thread(
            client.listen.v1.media.transcribe_file,
            request=str(audio_file),
            options=options,
            request_options={"timeout_in_seconds": int(timeout)},
        )

    async def health_check(self) -> dict[str, Any]:
        """Check Deepgram API health status.

        Returns:
            Health status dictionary
        """
        client = self._get_sdk_client()

        async def _check() -> dict[str, Any]:
            try:
                info = client.manage.v1.projects.get_projects()
                return {"status": "healthy", "project_count": len(info.get("projects", []))}
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}

        return await self._execute_with_retry(
            _check,
            context={"operation": "health_check", "provider": "deepgram"},
        )


__all__ = ["DeepgramAPIClient"]
