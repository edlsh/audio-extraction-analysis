"""
Test data management for E2E testing.

This module handles:
- Test media file generation
- Edge case file creation
- Test data cleanup
- File validation utilities
"""

import os
import subprocess
from pathlib import Path


class TestDataManager:
    """Manages test media files and data for E2E testing."""

    def __init__(self, test_data_dir: Path | None = None):
        """Initialize test data manager."""
        self.test_data_dir = test_data_dir or Path(__file__).parent / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)

        # Test file specifications
        self.test_files = {
            "short": {
                "name": "test_short.mp4",
                "duration": 5,
                "size_mb": 1,
                "description": "Basic functionality testing",
            },
            "medium": {
                "name": "test_medium.mp4",
                "duration": 120,  # 2 minutes
                "size_mb": 20,
                "description": "Standard workflow testing",
            },
            "long": {
                "name": "test_long.mp4",
                "duration": 1800,  # 30 minutes
                "size_mb": 300,
                "description": "Performance testing",
            },
            "audio_only": {
                "name": "test_audio.mp3",
                "duration": 10,
                "size_mb": 0.2,
                "description": "Audio-only pipeline",
            },
        }

        # Edge case files
        self.edge_case_files = {
            "empty": {"name": "test_empty.mp4", "size": 0, "description": "Empty file edge case"},
            "corrupted": {
                "name": "test_corrupted.mp4",
                "size": 1024,  # 1KB of random data
                "description": "Corrupted media file",
            },
            "unicode": {
                "name": "test_unicode_名前.mp4",
                "duration": 5,
                "description": "Unicode filename support",
            },
            "spaces": {
                "name": "test spaces.mp4",
                "duration": 5,
                "description": "Filename with spaces",
            },
            "special_chars": {
                "name": "test@#$%file.mp4",
                "duration": 5,
                "description": "Special characters in filename",
            },
            "large": {
                "name": "test_large.mp4",
                "duration": 3600,  # 1 hour
                "size_mb": 1000,  # 1GB
                "description": "Large file stress test",
            },
        }

    def generate_all_test_files(self, force_regenerate: bool = False) -> dict[str, Path]:
        """Generate all required test files."""
        generated_files = {}

        # Generate standard test files
        for file_key, spec in self.test_files.items():
            file_path = self._generate_test_media(spec, force_regenerate)
            if file_path:
                generated_files[file_key] = file_path

        # Generate edge case files
        for file_key, spec in self.edge_case_files.items():
            file_path = self._generate_edge_case_file(spec, force_regenerate)
            if file_path:
                generated_files[f"edge_{file_key}"] = file_path

        return generated_files

    def _generate_test_media(self, spec: dict, force_regenerate: bool = False) -> Path | None:
        """Generate a test media file using FFmpeg."""
        file_path = self.test_data_dir / spec["name"]

        if file_path.exists() and not force_regenerate:
            return file_path

        # Check if FFmpeg is available
        if not self._check_ffmpeg_available():
            print(f"Warning: FFmpeg not available, skipping {spec['name']}")
            return None

        try:
            duration = spec["duration"]

            # Generate synthetic video with audio
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={duration}:size=320x240:rate=1",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=1000:duration={duration}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
                str(file_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0 and file_path.exists():
                print(f"Generated test file: {file_path}")
                return file_path
            else:
                print(f"Failed to generate {spec['name']}: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print(f"Timeout generating {spec['name']}")
            return None
        except Exception as e:
            print(f"Error generating {spec['name']}: {e}")
            return None

    def _generate_edge_case_file(
        self, spec: dict, force_regenerate: bool = False
    ) -> Path | None:
        """Generate edge case test files."""
        file_path = self.test_data_dir / spec["name"]

        if file_path.exists() and not force_regenerate:
            return file_path

        try:
            if "empty" in spec["name"]:
                # Create empty file
                file_path.touch()

            elif "corrupted" in spec["name"]:
                # Create file with random data
                with open(file_path, "wb") as f:
                    f.write(os.urandom(spec["size"]))

            elif (
                "unicode" in spec["name"]
                or "spaces" in spec["name"]
                or "special_chars" in spec["name"]
            ):
                # Create small valid media file with special filename
                if self._check_ffmpeg_available():
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc=duration=5:size=320x240:rate=1",
                        "-f",
                        "lavfi",
                        "-i",
                        "sine=frequency=1000:duration=5",
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-shortest",
                        str(file_path),
                    ]

                    subprocess.run(cmd, capture_output=True, timeout=60)
                else:
                    # Fallback: create dummy file
                    with open(file_path, "wb") as f:
                        f.write(b"dummy_media_data" * 100)

            elif "large" in spec["name"]:
                # For large files, create a placeholder unless specifically requested
                with open(file_path, "wb") as f:
                    f.write(b"LARGE_FILE_PLACEHOLDER")
                print(f"Created placeholder for large file: {file_path}")
                print("Use generate_large_file() method to create actual large file")

            if file_path.exists():
                print(f"Generated edge case file: {file_path}")
                return file_path

        except Exception as e:
            print(f"Error generating edge case file {spec['name']}: {e}")
            return None

        return None

    def generate_large_file(self) -> Path | None:
        """Generate actual large file for stress testing (slow operation)."""
        spec = self.edge_case_files["large"]
        file_path = self.test_data_dir / spec["name"]

        if not self._check_ffmpeg_available():
            print("FFmpeg required for large file generation")
            return None

        print(f"Generating large file {spec['name']} (this may take several minutes)...")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={spec['duration']}:size=1920x1080:rate=30",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=1000:duration={spec['duration']}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
                str(file_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3600
            )  # 1 hour timeout

            if result.returncode == 0:
                print(f"Large file generated: {file_path}")
                return file_path
            else:
                print(f"Failed to generate large file: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("Timeout generating large file")
            return None
        except Exception as e:
            print(f"Error generating large file: {e}")
            return None

    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available in system PATH."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_test_file_path(self, file_type: str) -> Path | None:
        """Get path to a specific test file."""
        if file_type in self.test_files:
            return self.test_data_dir / self.test_files[file_type]["name"]
        elif file_type in self.edge_case_files:
            return self.test_data_dir / self.edge_case_files[file_type]["name"]
        return None

    def validate_test_files(self) -> dict[str, bool]:
        """Validate that test files exist and are accessible."""
        validation_results = {}

        # Check standard test files
        for file_key, spec in self.test_files.items():
            file_path = self.test_data_dir / spec["name"]
            validation_results[file_key] = file_path.exists() and file_path.stat().st_size > 0

        # Check edge case files
        for file_key, spec in self.edge_case_files.items():
            file_path = self.test_data_dir / spec["name"]
            exists = file_path.exists()
            # For empty file, just check existence
            if "empty" in spec["name"]:
                validation_results[f"edge_{file_key}"] = exists
            else:
                validation_results[f"edge_{file_key}"] = exists and file_path.stat().st_size > 0

        return validation_results

    def cleanup_test_files(self, keep_generated: bool = True):
        """Clean up test files."""
        if not keep_generated:
            import shutil

            if self.test_data_dir.exists():
                shutil.rmtree(self.test_data_dir)
                print(f"Cleaned up test data directory: {self.test_data_dir}")
        else:
            # Only clean up temporary files, keep generated media
            temp_patterns = ["*.tmp", "*.temp", "*_temp_*"]
            for pattern in temp_patterns:
                for temp_file in self.test_data_dir.glob(pattern):
                    temp_file.unlink()

    def get_file_specs(self) -> dict[str, dict]:
        """Get specifications for all test files."""
        return {"standard": self.test_files, "edge_cases": self.edge_case_files}

    def create_custom_test_file(
        self, name: str, duration: int = 10, video_size: str = "640x480", audio_freq: int = 1000
    ) -> Path | None:
        """Create a custom test file with specified parameters."""
        if not self._check_ffmpeg_available():
            print("FFmpeg required for custom file generation")
            return None

        file_path = self.test_data_dir / name

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={duration}:size={video_size}:rate=30",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={audio_freq}:duration={duration}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
                str(file_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                print(f"Custom test file created: {file_path}")
                return file_path
            else:
                print(f"Failed to create custom file: {result.stderr}")
                return None

        except Exception as e:
            print(f"Error creating custom file: {e}")
            return None


def setup_test_data() -> TestDataManager:
    """Setup and initialize test data for E2E tests."""
    manager = TestDataManager()

    print("Setting up test data...")
    generated_files = manager.generate_all_test_files()

    print(f"Generated {len(generated_files)} test files:")
    for file_type, file_path in generated_files.items():
        print(f"  {file_type}: {file_path}")

    # Validate generated files
    validation_results = manager.validate_test_files()
    failed_files = [k for k, v in validation_results.items() if not v]

    if failed_files:
        print(f"Warning: Some test files failed validation: {failed_files}")
    else:
        print("All test files validated successfully")

    return manager


if __name__ == "__main__":
    # Setup test data when run directly
    setup_test_data()
