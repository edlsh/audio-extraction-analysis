"""Comprehensive tests for path sanitization and traversal prevention.

This module covers:
- Path traversal attack prevention
- Filename sanitization (special chars, unicode, length limits)
- ensure_subpath containment validation
- Property-based style tests using parametrize for fuzzing paths
"""

from __future__ import annotations

import os
import string
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.paths import ensure_subpath
from src.utils.sanitization import (
    PathSanitizer,
    sanitize_dirname,
    sanitize_filename,
    sanitize_path,
)


class TestPathTraversalPrevention:
    """Test path traversal attack prevention."""

    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../etc/passwd",
            "../../secret.txt",
            "../../../home/user/.ssh/id_rsa",
            "foo/../../../etc/shadow",
            "a/b/c/../../../../../../../etc/hosts",
            "foo/..\\bar/../../../etc",  # Mixed (forward slashes processed, backslash literal)
        ],
    )
    def test_ensure_subpath_blocks_traversal_attacks(
        self, tmp_path: Path, malicious_path: str
    ) -> None:
        """Test that path traversal attacks are blocked by ensure_subpath."""
        with pytest.raises(ValueError, match="escapes root"):
            ensure_subpath(tmp_path, malicious_path)

    @pytest.mark.parametrize(
        "edge_case_path",
        [
            # Windows-style backslashes on Unix are literal chars, not separators
            "..\\windows\\system32",
            # URL-encoded paths are NOT decoded by filesystem - these are literal strings
            "%2e%2e/%2e%2e/etc/passwd",
            # Double dots are not treated as special
            "....//....//etc/passwd",
        ],
    )
    def test_edge_case_paths_not_traversals_on_unix(
        self, tmp_path: Path, edge_case_path: str
    ) -> None:
        """Test paths that look dangerous but aren't traversals on Unix.

        On Unix, backslashes are literal characters (not path separators),
        URL encoding is not decoded by the filesystem, and multiple dots
        are just regular directory names.
        """
        # These should NOT raise on Unix - they create strange but valid paths
        result = ensure_subpath(tmp_path, edge_case_path)
        # The result should still be within tmp_path
        assert str(result).startswith(str(tmp_path.resolve()))

    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../escape",
            "../../double_escape",
            "nested/../../../escape",
            "./../mixed",
        ],
    )
    def test_ensure_safe_subpath_blocks_traversal(
        self, tmp_path: Path, malicious_path: str
    ) -> None:
        """Test PathSanitizer.ensure_safe_subpath raises ValueError on path escape."""
        # ensure_safe_subpath now raises ValueError on path escape (reject semantics)
        with pytest.raises(ValueError, match="Path escapes root"):
            PathSanitizer.ensure_safe_subpath(tmp_path, malicious_path)

    def test_ensure_subpath_allows_valid_nested_paths(self, tmp_path: Path) -> None:
        """Test that valid nested paths are allowed."""
        valid_path = "subdir/nested/file.txt"
        result = ensure_subpath(tmp_path, valid_path)
        assert result == (tmp_path / valid_path).resolve()
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_ensure_subpath_with_absolute_subpath_inside_root(self, tmp_path: Path) -> None:
        """Test behavior with absolute path that is inside root."""
        # Create the target path within tmp_path
        inner_path = tmp_path / "inner" / "file.txt"
        inner_path.parent.mkdir(parents=True, exist_ok=True)
        inner_path.touch()

        # Using relative path to this location should work
        result = ensure_subpath(tmp_path, "inner/file.txt")
        assert result.exists()

    def test_symlink_traversal_blocked(self, tmp_path: Path) -> None:
        """Test that symlinks pointing outside root are handled."""
        # Create a symlink pointing outside
        inner_dir = tmp_path / "inner"
        inner_dir.mkdir()
        secret_dir = tmp_path.parent / "secret_location"
        secret_dir.mkdir(exist_ok=True)
        secret_file = secret_dir / "secret.txt"
        secret_file.write_text("secret")

        # Create symlink inside tmp_path pointing outside
        symlink_path = inner_dir / "escape_link"
        try:
            symlink_path.symlink_to(secret_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Following the symlink via ensure_subpath should fail because
        # the resolved path escapes the root
        with pytest.raises(ValueError, match="escapes root"):
            ensure_subpath(tmp_path, "inner/escape_link/secret.txt")


class TestFilenameSpecialCharacters:
    """Test filename sanitization with special characters."""

    @pytest.mark.parametrize(
        "input_name,expected_contains",
        [
            ("normal.txt", "normal.txt"),
            ("file with spaces.txt", "file with spaces.txt"),
            ("file-with-dashes.txt", "file-with-dashes.txt"),
            ("file_with_underscores.txt", "file_with_underscores.txt"),
            ("file.multiple.dots.txt", "file.multiple.dots.txt"),
        ],
    )
    def test_valid_filenames_preserved(self, input_name: str, expected_contains: str) -> None:
        """Test that valid filenames are preserved."""
        result = PathSanitizer.sanitize_filename(input_name)
        assert expected_contains in result or result == expected_contains

    @pytest.mark.parametrize(
        "input_name",
        [
            "file:colon.txt",
            "file*star.txt",
            "file?question.txt",
            "file<less.txt",
            "file>greater.txt",
            'file"quote.txt',
            "file|pipe.txt",
            "file\x00null.txt",  # NULL byte
            "file\nnewline.txt",
            "file\ttab.txt",
            "file\rcarriage.txt",
        ],
    )
    def test_invalid_chars_replaced(self, input_name: str) -> None:
        """Test that invalid characters are replaced."""
        result = PathSanitizer.sanitize_filename(input_name)
        # Result should not contain the dangerous characters
        for char in ':*?<>"|':
            if char != "_":
                assert char not in result, f"Character {char!r} should be replaced"
        # No control characters
        assert "\x00" not in result
        assert "\n" not in result
        assert "\t" not in result
        assert "\r" not in result

    @pytest.mark.parametrize(
        "input_name",
        [
            "file$shell.txt",
            "file;semicolon.txt",
            "file&ampersand.txt",
            "file`backtick.txt",
            "file$(command).txt",
            "file`whoami`.txt",
        ],
    )
    def test_shell_metacharacters_replaced(self, input_name: str) -> None:
        """Test that shell metacharacters are replaced in filenames."""
        result = PathSanitizer.sanitize_filename(input_name)
        # These dangerous shell chars should be replaced
        for char in "$;`&":
            assert char not in result, f"Shell metachar {char!r} should be replaced"


class TestFilenameUnicode:
    """Test filename sanitization with unicode characters."""

    @pytest.mark.parametrize(
        "input_name",
        [
            "café.txt",  # Latin-1 supplement
            "日本語.txt",  # Japanese
            "中文.txt",  # Chinese
            "한국어.txt",  # Korean
            "Ελληνικά.txt",  # Greek
            "العربية.txt",  # Arabic
            "🎵music.txt",  # Emoji
            "файл.txt",  # Cyrillic
        ],
    )
    def test_unicode_filenames_handled(self, input_name: str) -> None:
        """Test that unicode filenames are handled (replaced with safe chars)."""
        result = PathSanitizer.sanitize_filename(input_name)
        # Result should be non-empty and safe for filesystem
        assert len(result) > 0
        # Should contain the extension if it was ASCII
        if input_name.endswith(".txt"):
            assert result.endswith(".txt") or "_" in result

    def test_empty_after_sanitization_gets_default(self) -> None:
        """Test that empty result after sanitization gets a default name."""
        # Filename with only invalid characters
        result = PathSanitizer.sanitize_filename(":::***???")
        assert result == "unnamed"

    def test_unicode_normalization_equivalent_forms(self) -> None:
        """Test handling of unicode normalization forms."""
        # NFD vs NFC forms of é (e + combining acute vs precomposed)
        nfd_form = "caf\u0065\u0301.txt"  # e + combining acute accent
        nfc_form = "caf\u00e9.txt"  # precomposed é

        result_nfd = PathSanitizer.sanitize_filename(nfd_form)
        result_nfc = PathSanitizer.sanitize_filename(nfc_form)

        # Both should produce valid non-empty results
        assert len(result_nfd) > 0
        assert len(result_nfc) > 0


class TestFilenameLengthLimits:
    """Test filename length limit handling."""

    def test_short_filename_unchanged(self) -> None:
        """Test that short filenames are not modified for length."""
        short_name = "short.txt"
        result = PathSanitizer.sanitize_filename(short_name)
        assert result == short_name

    def test_long_filename_truncated(self) -> None:
        """Test that very long filenames are truncated."""
        long_name = "a" * 300 + ".txt"
        result = PathSanitizer.sanitize_filename(long_name)
        # Max length is 200 characters
        assert len(result) <= 200
        # Extension should be preserved
        assert result.endswith(".txt")

    def test_long_filename_without_extension_truncated(self) -> None:
        """Test truncation of long filename without extension."""
        long_name = "a" * 300
        result = PathSanitizer.sanitize_filename(long_name)
        assert len(result) <= 200

    def test_very_long_extension_handled(self) -> None:
        """Test handling of very long extensions."""
        long_ext_name = "file." + "a" * 50
        result = PathSanitizer.sanitize_filename(long_ext_name)
        # Long extensions (>10 chars) are not preserved specially
        assert len(result) <= 200

    @pytest.mark.parametrize("length", [199, 200, 201, 250, 255, 300])
    def test_boundary_lengths(self, length: int) -> None:
        """Test filename length at various boundaries."""
        name = "a" * length
        result = PathSanitizer.sanitize_filename(name)
        assert len(result) <= 200


class TestDirnameSanitization:
    """Test directory name sanitization."""

    def test_valid_dirname_preserved(self) -> None:
        """Test that valid directory names are preserved."""
        valid_names = ["subdir", "my-folder", "folder_name", "123"]
        for name in valid_names:
            result = PathSanitizer.sanitize_dirname(name)
            assert result == name

    def test_dirname_more_restrictive_than_filename(self) -> None:
        """Test that dirname is more restrictive (no dots)."""
        # Dots are allowed in filenames but not in dirnames
        result = PathSanitizer.sanitize_dirname("folder.name")
        assert "." not in result or result.count("_") > 0

    def test_empty_dirname_gets_default(self) -> None:
        """Test that empty dirname gets default value."""
        result = PathSanitizer.sanitize_dirname("...")
        assert result == "unnamed_dir"

    def test_dirname_length_limit(self) -> None:
        """Test that directory names are truncated appropriately."""
        long_name = "a" * 150
        result = PathSanitizer.sanitize_dirname(long_name)
        assert len(result) <= 100


class TestPathSecurityValidation:
    """Test path security validation."""

    def test_nul_byte_rejected(self) -> None:
        """Test that NUL bytes in paths are rejected."""
        with pytest.raises(ValueError, match="NUL byte"):
            PathSanitizer.validate_path_security(Path("/path/with\x00null"))

    @pytest.mark.parametrize(
        "control_char",
        ["\x01", "\x02", "\x07", "\x0b", "\x0c", "\x1b"],
    )
    def test_control_chars_rejected(self, control_char: str) -> None:
        """Test that control characters in paths are rejected."""
        with pytest.raises(ValueError, match="control characters"):
            PathSanitizer.validate_path_security(Path(f"/path/with{control_char}char"))

    @pytest.mark.parametrize(
        "shell_char",
        [";", "&", "|", "`", "$", "<", ">"],
    )
    def test_shell_metacharacters_rejected(self, shell_char: str) -> None:
        """Test that shell metacharacters are rejected."""
        with pytest.raises(ValueError, match="Invalid characters"):
            PathSanitizer.validate_path_security(Path(f"/path/with{shell_char}char"))

    def test_normal_paths_pass_validation(self, tmp_path: Path) -> None:
        """Test that normal paths pass validation."""
        valid_paths = [
            tmp_path / "normal.txt",
            tmp_path / "path" / "to" / "file.txt",
            tmp_path / "file with spaces.txt",
            tmp_path / "file-with-dashes.txt",
            tmp_path / "file[with]brackets.txt",
            tmp_path / "file(with)parens.txt",
        ]
        for path in valid_paths:
            # Should not raise
            PathSanitizer.validate_path_security(path)


class TestSubprocessPathSanitization:
    """Test subprocess path sanitization."""

    def test_path_quoted_for_subprocess(self, tmp_path: Path) -> None:
        """Test that paths are properly quoted for subprocess."""
        path = tmp_path / "file with spaces.txt"
        result = PathSanitizer.sanitize_for_subprocess(path)
        # Should be quoted
        assert "'" in result or '"' in result

    def test_special_chars_escaped(self, tmp_path: Path) -> None:
        """Test that special characters are escaped for subprocess."""
        path = tmp_path / "file$name&test.txt"
        result = PathSanitizer.sanitize_for_subprocess(path)
        # Result should be safely quoted
        assert isinstance(result, str)

    def test_relative_path_made_absolute(self) -> None:
        """Test that relative paths are converted to absolute."""
        result = PathSanitizer.sanitize_for_subprocess("./relative/path.txt")
        # Should contain absolute path
        unquoted = result.strip("'\"")
        assert unquoted.startswith("/")


class TestPropertyBasedFuzzing:
    """Property-based style tests using parametrize for fuzzing paths.

    These tests simulate property-based testing by testing many random-like inputs.
    """

    @pytest.mark.parametrize(
        "random_suffix",
        [
            # Alphanumeric patterns
            "abc123",
            "XYZ789",
            "".join([c for c in string.ascii_letters[:26]]),
            # Special character patterns
            "___",
            "---",
            "...",
            "   ",
            # Mixed patterns
            "a b c",
            "1-2-3",
            "x_y_z",
            # Edge cases
            "",
            " ",
            ".",
            "..",
        ],
    )
    def test_sanitize_filename_never_returns_empty_for_valid_input(
        self, random_suffix: str
    ) -> None:
        """Test that filename sanitization always returns non-empty result."""
        input_name = f"file{random_suffix}.txt"
        result = PathSanitizer.sanitize_filename(input_name)
        assert len(result) > 0

    @pytest.mark.parametrize(
        "traversal_attempt",
        [
            # Basic traversal - these all escape root
            *[f"{'../' * i}secret" for i in range(1, 10)],
            # With prefix that gets cancelled - need 2+ to escape
            *[f"safe/{'../' * i}escape" for i in range(2, 10)],
        ],
    )
    def test_ensure_subpath_blocks_all_traversal_variants(
        self, tmp_path: Path, traversal_attempt: str
    ) -> None:
        """Test that all path traversal variants are blocked."""
        with pytest.raises(ValueError, match="escapes root"):
            ensure_subpath(tmp_path, traversal_attempt)

    @pytest.mark.parametrize(
        "safe_traversal",
        [
            # safe/../escape resolves to just "escape" which is within root
            "safe/../escape",
            # Pure backslashes on Unix are literal characters - no forward slash means no real traversal
            "..\\..\\secret",
            # URL encoding is NOT decoded - these are literal directory names
            "%2e%2e%2f%2e%2e%2f",
            "%252e%252e%252f",
        ],
    )
    def test_path_patterns_that_stay_within_root(self, tmp_path: Path, safe_traversal: str) -> None:
        """Test paths that normalize to stay within root.

        These look like traversals but actually resolve to valid paths
        within the root directory on Unix systems.
        """
        result = ensure_subpath(tmp_path, safe_traversal)
        assert str(result).startswith(str(tmp_path.resolve()))

    @pytest.mark.parametrize(
        "mixed_traversal",
        [
            # Mixed: forward slash triggers Unix traversal even if backslash follows
            "../..\\secret",
        ],
    )
    def test_mixed_slash_traversals_blocked(self, tmp_path: Path, mixed_traversal: str) -> None:
        """Test that forward-slash traversals are blocked even with backslashes."""
        with pytest.raises(ValueError, match="escapes root"):
            ensure_subpath(tmp_path, mixed_traversal)

    @pytest.mark.parametrize(
        "char_code",
        # Test all control characters 0x00-0x1f
        list(range(0x00, 0x20)),
    )
    def test_control_characters_handled_in_filename(self, char_code: int) -> None:
        """Test that all control characters are handled in filenames."""
        char = chr(char_code)
        input_name = f"file{char}name.txt"
        result = PathSanitizer.sanitize_filename(input_name)
        # Result should not contain the control character
        assert char not in result or char == "_"

    @pytest.mark.parametrize(
        "length",
        [1, 10, 50, 100, 150, 200, 255, 500, 1000],
    )
    def test_filename_length_invariant(self, length: int) -> None:
        """Test that filename output length is always bounded."""
        input_name = "x" * length + ".txt"
        result = PathSanitizer.sanitize_filename(input_name)
        # Max 200 chars or original if shorter
        assert len(result) <= 200


class TestSafeOutputPath:
    """Test safe output path generation."""

    def test_generates_safe_output_path(self, tmp_path: Path) -> None:
        """Test safe output path generation."""
        input_path = tmp_path / "input.wav"
        input_path.touch()

        result = PathSanitizer.get_safe_output_path(input_path, suffix=".txt")
        assert result.parent == tmp_path
        assert result.suffix == ".txt"
        assert "input" in result.stem

    def test_output_path_with_custom_dir(self, tmp_path: Path) -> None:
        """Test output path generation with custom directory."""
        input_path = tmp_path / "input.wav"
        input_path.touch()
        output_dir = tmp_path / "output"

        result = PathSanitizer.get_safe_output_path(
            input_path, output_dir=output_dir, suffix=".txt"
        )
        assert result.parent == output_dir
        assert output_dir.exists()

    def test_input_with_special_chars_sanitized(self, tmp_path: Path) -> None:
        """Test that input files with special chars are sanitized."""
        # Create input with special name
        input_path = tmp_path / "input$test.wav"
        input_path.touch()

        result = PathSanitizer.get_safe_output_path(input_path, suffix=".txt")
        # Should not contain $ in the output stem
        assert "$" not in result.stem


class TestBackwardCompatibility:
    """Test backward compatibility functions."""

    def test_sanitize_path_function(self, tmp_path: Path) -> None:
        """Test the backward-compatible sanitize_path function."""
        result = sanitize_path(tmp_path / "test.txt")
        assert isinstance(result, str)

    def test_sanitize_filename_function(self) -> None:
        """Test the backward-compatible sanitize_filename function."""
        result = sanitize_filename("test:file.txt")
        assert ":" not in result

    def test_sanitize_dirname_function(self) -> None:
        """Test the backward-compatible sanitize_dirname function."""
        result = sanitize_dirname("test.dir")
        # Dots replaced in dirname
        assert isinstance(result, str)
        assert len(result) > 0


class TestEnsureSubpathEdgeCases:
    """Edge case tests for ensure_subpath."""

    def test_root_path_normalization(self, tmp_path: Path) -> None:
        """Test that root path is normalized."""
        # Using relative-like path for root
        result = ensure_subpath(tmp_path, "file.txt")
        assert result.is_absolute()

    def test_subpath_with_current_dir_reference(self, tmp_path: Path) -> None:
        """Test subpath with current directory reference."""
        result = ensure_subpath(tmp_path, "./file.txt")
        assert result == (tmp_path / "file.txt").resolve()

    def test_empty_subpath(self, tmp_path: Path) -> None:
        """Test empty subpath."""
        result = ensure_subpath(tmp_path, "")
        assert result == tmp_path.resolve()

    def test_subpath_with_trailing_slash(self, tmp_path: Path) -> None:
        """Test subpath with trailing slash."""
        result = ensure_subpath(tmp_path, "subdir/")
        assert result == (tmp_path / "subdir").resolve()

    def test_multiple_slashes_normalized(self, tmp_path: Path) -> None:
        """Test that multiple slashes are normalized."""
        result = ensure_subpath(tmp_path, "a//b///c")
        assert result == (tmp_path / "a" / "b" / "c").resolve()
