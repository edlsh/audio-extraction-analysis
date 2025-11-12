"""Path sanitization utilities for safe subprocess and file operations."""

from __future__ import annotations

import re
import shlex
from pathlib import Path


class PathSanitizer:
    """Utilities for sanitizing file paths for safe usage."""

    @staticmethod
    def sanitize_for_subprocess(file_path: Path | str) -> str:
        """Sanitize file path for safe subprocess usage.

        Uses shlex.quote to properly escape special characters for shell commands.

        Args:
            file_path: Path to sanitize (Path object or string)

        Returns:
            Safely quoted path string for subprocess usage
        """
        if isinstance(file_path, Path):
            path_str = str(file_path.resolve())
        else:
            path_str = str(Path(file_path).resolve())

        return shlex.quote(path_str)

    @staticmethod
    def sanitize_filename(filename: str, replacement: str = "_") -> str:
        """Sanitize a filename by replacing invalid characters.

        Args:
            filename: Original filename
            replacement: Character to replace invalid chars with (default: underscore)

        Returns:
            Sanitized filename safe for filesystem operations
        """
        # Remove or replace invalid filename characters
        # Keep alphanumeric, dots, hyphens, underscores, and spaces
        sanitized = re.sub(r"[^\w\s.-]", replacement, filename)

        # Remove multiple consecutive replacements
        if replacement:
            sanitized = re.sub(f"{re.escape(replacement)}+", replacement, sanitized)

        # Trim leading/trailing whitespace and replacement chars
        sanitized = sanitized.strip(f" {replacement}")

        # Ensure filename is not empty
        if not sanitized:
            sanitized = "unnamed"

        # Limit length to avoid filesystem issues (255 chars is common limit)
        max_length = 200  # Leave room for extensions
        if len(sanitized) > max_length:
            # Preserve extension if present
            parts = sanitized.rsplit(".", 1)
            if len(parts) == 2 and len(parts[1]) <= 10:  # Has reasonable extension
                name_part = parts[0][: max_length - len(parts[1]) - 1]
                sanitized = f"{name_part}.{parts[1]}"
            else:
                sanitized = sanitized[:max_length]

        return sanitized

    @staticmethod
    def sanitize_dirname(dirname: str, replacement: str = "_") -> str:
        """Sanitize a directory name by replacing invalid characters.

        Args:
            dirname: Original directory name
            replacement: Character to replace invalid chars with (default: underscore)

        Returns:
            Sanitized directory name safe for filesystem operations
        """
        # Similar to filename but more restrictive
        # Remove or replace invalid directory name characters
        sanitized = re.sub(r"[^\w\s-]", replacement, dirname)

        # Remove multiple consecutive replacements
        if replacement:
            sanitized = re.sub(f"{re.escape(replacement)}+", replacement, sanitized)

        # Trim leading/trailing whitespace and replacement chars
        sanitized = sanitized.strip(f" {replacement}")

        # Ensure dirname is not empty
        if not sanitized:
            sanitized = "unnamed_dir"

        # Limit length
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip(replacement)

        return sanitized

    @staticmethod
    def ensure_safe_subpath(base_path: Path, subpath: str) -> Path:
        """Ensure a subpath doesn't escape the base directory (prevent path traversal).

        Args:
            base_path: Base directory that should contain the result
            subpath: Subpath to join with base_path

        Returns:
            Safe path that is guaranteed to be within base_path

        Raises:
            ValueError: If the resulting path would escape base_path
        """
        base_path = base_path.resolve()

        # Sanitize the subpath to remove any '..' components
        clean_subpath = Path(subpath)
        parts = []
        for part in clean_subpath.parts:
            if part == "..":
                continue  # Skip parent directory references
            elif part == ".":
                continue  # Skip current directory references
            else:
                parts.append(part)

        # Construct the full path
        full_path = base_path
        for part in parts:
            full_path = full_path / part

        # Resolve and verify it's still within base_path
        resolved = full_path.resolve()
        try:
            resolved.relative_to(base_path)
        except ValueError:
            raise ValueError(f"Path traversal detected: {subpath} would escape {base_path}")

        return resolved

    @staticmethod
    def validate_path_security(path: Path) -> None:
        """Basic security validation for filesystem paths.

        Checks for common dangerous characters that could impact shell execution
        or indicate injection attempts. This does not replace comprehensive
        sandboxing or ACL checks but provides a sane baseline.

        Args:
            path: Path to validate

        Raises:
            ValueError: If the path contains disallowed characters
        """
        s = str(Path(path))
        # Disallow NUL bytes and control characters
        if "\x00" in s:
            raise ValueError("Path contains NUL byte")
        if re.search(r"[\x00-\x1f]", s):
            raise ValueError("Path contains control characters")
        # Disallow shell metacharacters that are risky in many contexts
        # Note: square brackets and parentheses are allowed to keep common filenames working
        if re.search(r"[;&|`$<>]", s):
            raise ValueError("Invalid characters in file path")

    @staticmethod
    def get_safe_output_path(
        input_path: Path, output_dir: Path | None = None, suffix: str = ".output"
    ) -> Path:
        """Generate a safe output path based on input path.

        Args:
            input_path: Input file path
            output_dir: Optional output directory (default: same as input)
            suffix: New suffix for output file

        Returns:
            Safe output path
        """
        input_path = Path(input_path)

        # Determine output directory
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = input_path.parent

        # Create output filename
        sanitized_name = PathSanitizer.sanitize_filename(input_path.stem)
        output_path = out_dir / f"{sanitized_name}{suffix}"

        return output_path


# Convenience functions for backward compatibility
def sanitize_path(file_path: Path | str) -> str:
    """Sanitize file path for safe subprocess usage.

    Args:
        file_path: Path to sanitize

    Returns:
        Safely quoted path string
    """
    return PathSanitizer.sanitize_for_subprocess(file_path)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by replacing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    return PathSanitizer.sanitize_filename(filename)


def sanitize_dirname(dirname: str) -> str:
    """Sanitize a directory name by replacing invalid characters.

    Args:
        dirname: Original directory name

    Returns:
        Sanitized directory name
    """
    return PathSanitizer.sanitize_dirname(dirname)
