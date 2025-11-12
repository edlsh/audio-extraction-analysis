#!/usr/bin/env python3
"""
Example script demonstrating how to use the Parakeet transcription provider.

Parakeet is a high-performance speech-to-text transcription service that provides
async transcription capabilities. This example shows:
- How to create and initialize a Parakeet provider instance
- How to perform health checks before transcription
- How to transcribe audio files using the provider

Prerequisites:
- Parakeet service must be running and accessible
- Configuration should be set up in your environment
- Audio files should be in supported formats (mp3, wav, m4a, etc.)

Usage:
    python examples/parakeet_example.py
"""

import asyncio

from src.providers.factory import TranscriptionProviderFactory


async def main() -> None:
    """
    Demonstrate basic Parakeet provider usage with health check and setup.

    This function demonstrates the recommended workflow:
    1. Create the provider instance using the factory pattern
    2. Verify the provider is healthy and ready to accept requests
    3. Optionally transcribe audio files (commented example included)

    The function includes comprehensive error handling to gracefully handle
    provider initialization failures and unhealthy service states.
    """

    # Step 1: Create Parakeet provider instance using the factory
    # The factory pattern ensures proper initialization and configuration loading
    try:
        provider = TranscriptionProviderFactory.create_provider("parakeet")
        print(f"Created provider: {provider.get_provider_name()}")
    except Exception as e:
        print(f"Failed to create Parakeet provider: {e}")
        print("Ensure Parakeet service is running and properly configured.")
        return

    # Step 2: Verify provider health before attempting transcription
    # Health checks ensure the service is accessible and ready to process requests
    try:
        health = await provider.health_check_async()
        print(f"Provider health: {health['status']}")
        if not health["healthy"]:
            print("Provider is not healthy, exiting")
            print(f"Health details: {health}")
            return
    except Exception as e:
        print(f"Health check failed: {e}")
        print("Ensure Parakeet service endpoint is accessible.")
        return

    # Step 3: Transcribe audio files (example - uncomment to use)
    # To transcribe an actual audio file, uncomment and modify the following:
    #
    # audio_file_path = Path("path/to/your/audio/file.mp3")
    #
    # # Ensure the file exists before attempting transcription
    # if not audio_file_path.exists():
    #     print(f"Audio file not found: {audio_file_path}")
    #     return
    #
    # # Transcribe with optional language specification
    # try:
    #     result = await provider.transcribe_async(
    #         audio_file_path,
    #         language="en"  # Optional: specify language code (en, es, fr, etc.)
    #     )
    #     print(f"Transcription result: {result['text']}")
    #     print(f"Confidence: {result.get('confidence', 'N/A')}")
    # except Exception as e:
    #     print(f"Transcription failed: {e}")
    #     return

    print("Parakeet provider setup complete!")
    print("To transcribe audio, uncomment the example code above and provide an audio file path.")


if __name__ == "__main__":
    asyncio.run(main())
