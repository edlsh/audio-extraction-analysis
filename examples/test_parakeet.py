#!/usr/bin/env python3
"""
Test script to demonstrate the Parakeet transcription provider.

This script provides a basic example of how to initialize and test the Parakeet
ASR (Automatic Speech Recognition) provider from the transcription framework.

Usage:
    python examples/test_parakeet.py

Requirements:
    - PyTorch and torchaudio installed
    - Parakeet provider properly configured
    - CUDA-capable GPU recommended (but not required)

What This Script Does:
    1. Generates a synthetic audio file (440 Hz sine wave tone)
    2. Initializes the Parakeet transcription provider
    3. Performs a health check to verify the provider is working
    4. Demonstrates provider capabilities and features
    5. Cleans up temporary files

Note:
    This is a demonstration script that generates synthetic audio (sine wave tone)
    rather than actual speech. For real transcription testing, replace the
    create_test_audio() function with actual speech audio files.

Expected Output:
    - Provider initialization confirmation
    - Health check status (should be healthy)
    - Supported features list
    - Test audio file path
"""

import asyncio
import tempfile
from pathlib import Path

import torch
import torchaudio

from src.providers.factory import TranscriptionProviderFactory


async def create_test_audio():
    """
    Create a synthetic test audio file for demonstration purposes.

    Generates a 3-second mono audio file containing a 440 Hz sine wave (A4 note)
    with added Gaussian noise. The audio is saved as a temporary WAV file.

    Returns:
        Path: Absolute path to the generated temporary WAV file.

    Technical Details:
        - Sample Rate: 16000 Hz (standard for speech recognition)
        - Duration: 3 seconds
        - Frequency: 440 Hz (A4 musical note)
        - Channels: 1 (mono)
        - Noise: Gaussian noise at 10% amplitude for realism

    Note:
        This generates a pure tone, not speech. It's intended for testing
        provider initialization and health checks, not actual transcription
        quality. The caller is responsible for deleting the temporary file.
    """
    # Create a simple sine wave tone as test audio
    sample_rate = 16000
    duration = 3  # seconds
    frequency = 440  # Hz (A4 note)

    # Generate time vector
    t = torch.linspace(0, duration, int(sample_rate * duration))

    # Generate sine wave
    waveform = torch.sin(2 * torch.pi * frequency * t)

    # Add some noise to make it more interesting
    noise = torch.randn_like(waveform) * 0.1
    waveform = waveform + noise

    # Normalize
    waveform = waveform / torch.max(torch.abs(waveform))

    # Add channel dimension (mono)
    waveform = waveform.unsqueeze(0)

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        torchaudio.save(tmp_file.name, waveform, sample_rate)
        return Path(tmp_file.name)


async def main():
    """
    Main test function to demonstrate Parakeet provider functionality.

    This function orchestrates the complete test workflow:
    1. Creates a synthetic audio file for testing
    2. Initializes the Parakeet transcription provider via the factory
    3. Retrieves and displays provider metadata (name, features)
    4. Performs a health check to verify provider readiness
    5. Cleans up temporary files when done

    The test validates that the provider can be initialized and is operational,
    but does not perform actual transcription since the audio is a synthetic
    tone rather than speech.

    Raises:
        Exception: If provider creation or health check fails.

    Note:
        Temporary audio files are automatically cleaned up in the finally block,
        even if an error occurs during testing.
    """
    print("Testing Parakeet transcription provider...")

    # Create synthetic test audio file (sine wave tone)
    print("Creating test audio file...")
    audio_path = await create_test_audio()

    try:
        # Initialize the Parakeet provider using the factory pattern
        print("Creating Parakeet provider...")
        provider = TranscriptionProviderFactory.create_provider("parakeet")
        print(f"Provider: {provider.get_provider_name()}")
        print(f"Supported features: {provider.get_supported_features()}")

        # Perform health check to verify model loading and GPU/CPU availability
        print("Checking provider health...")
        health = await provider.health_check_async()
        print(f"Health status: {health['status']}")
        if health["healthy"]:
            print("Provider is healthy and ready!")
        else:
            print(f"Provider is not healthy: {health['details']}")
            return

        # Display test information and limitations
        # Note: This script demonstrates provider initialization and health checking.
        # For actual transcription testing, you would:
        #   1. Replace create_test_audio() with real speech audio
        #   2. Call provider.transcribe_async(audio_path)
        #   3. Evaluate transcription results
        print(f"Test audio file created at: {audio_path}")
        print("\nNote: This is a synthetic sine wave tone, not actual speech.")
        print("Transcription is not performed in this demonstration.")
        print("For real transcription testing, use actual speech audio files.")

    finally:
        # Clean up temporary test audio file to avoid disk space accumulation
        if audio_path.exists():
            audio_path.unlink()
            print(f"Cleaned up test audio file: {audio_path}")


if __name__ == "__main__":
    # Entry point: Run the async main function when script is executed directly
    asyncio.run(main())
