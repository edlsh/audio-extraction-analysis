"""Audio preprocessing for Parakeet transcription."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.exceptions import ParakeetAudioError
from src.utils.logger import get_logger

from .deps import AUDIO_LIBS_AVAILABLE, librosa, sf

logger = get_logger(__name__)


class AudioPreprocessor:
    """Handles audio preprocessing for Parakeet models."""

    TARGET_SAMPLE_RATE = 16000

    @classmethod
    def preprocess_audio(cls, audio_path: Path) -> tuple[Path | None, float | None]:
        """Preprocess audio file for Parakeet transcription.

        Converts audio to 16kHz mono WAV format if needed.

        Args:
            audio_path: Path to input audio file

        Returns:
            Tuple of (processed_audio_path, duration_seconds)
            Returns (None, None) if preprocessing fails
        """
        if not AUDIO_LIBS_AVAILABLE:
            logger.error("Audio processing libraries not available")
            return None, None

        try:
            audio_data, sample_rate = librosa.load(
                str(audio_path),
                sr=None,
                mono=True,
            )

            duration = len(audio_data) / sample_rate

            if sample_rate != cls.TARGET_SAMPLE_RATE:
                logger.info(f"Resampling audio from {sample_rate}Hz to {cls.TARGET_SAMPLE_RATE}Hz")
                audio_data = librosa.resample(
                    audio_data, orig_sr=sample_rate, target_sr=cls.TARGET_SAMPLE_RATE
                )
                sample_rate = cls.TARGET_SAMPLE_RATE

            needs_preprocessing = (
                audio_path.suffix.lower() != ".wav" or sample_rate != cls.TARGET_SAMPLE_RATE
            )

            if needs_preprocessing:
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False, dir=audio_path.parent
                ) as tmp_file:
                    output_path = Path(tmp_file.name)

                sf.write(
                    str(output_path),
                    audio_data,
                    cls.TARGET_SAMPLE_RATE,
                    subtype="PCM_16",
                )

                logger.info(f"Preprocessed audio saved to {output_path}")
                return output_path, duration
            else:
                return audio_path, duration

        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            raise ParakeetAudioError(f"Failed to preprocess audio: {e}")

    @classmethod
    def validate_audio_file(cls, audio_path: Path) -> bool:
        """Validate that audio file can be processed."""
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return False

        if not audio_path.is_file():
            logger.error(f"Path is not a file: {audio_path}")
            return False

        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if audio_path.stat().st_size > max_size:
            logger.error(f"Audio file too large: {audio_path.stat().st_size} bytes")
            return False

        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Cannot validate audio format without librosa/soundfile")
            return True

        try:
            info = sf.info(str(audio_path))
            logger.debug(
                f"Audio file info: duration={info.duration}s, "
                f"samplerate={info.samplerate}Hz, channels={info.channels}"
            )
            return True
        except Exception as e:
            logger.error(f"Invalid audio file {audio_path}: {e}")
            return False

    @classmethod
    def cleanup_temp_file(cls, temp_path: Path | None) -> None:
        """Clean up temporary audio file."""
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")


__all__ = ["AudioPreprocessor"]
