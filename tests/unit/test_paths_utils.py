"""Unit tests for path utility functions.

This module tests critical path manipulation and validation utilities that ensure
secure file operations and prevent path traversal attacks:

- sanitize_dirname: Removes or replaces unsafe characters from directory names
- ensure_subpath: Validates that paths remain within a designated root directory
  (prevents directory traversal attacks)
- safe_write_json: Safely writes JSON data with automatic directory creation

These utilities are fundamental for secure file handling throughout the application.
"""

import builtins
import json
from pathlib import Path

import pytest

from src.utils.paths import ensure_subpath, safe_write_json, sanitize_dirname


class TestSanitizeDirname:
    """Tests for sanitize_dirname function.

    The sanitize_dirname function removes or replaces characters that are
    unsafe for directory names across different operating systems, including
    path separators, wildcards, and special filesystem characters.

    Re-exported from PathSanitizer utility class.
    """

    def test_sanitize_dirname_replaces_unsafe(self):
        """Test that unsafe characters are replaced in directory names.

        Verifies removal of:
        - Path separators: / and \
        - Path traversal: ..
        - Special characters: : * ? < > |
        """
        name = "../weird name/with\\seps:*?<>|"
        s = sanitize_dirname(name)
        assert s  # Result should be non-empty
        assert "/" not in s and "\\" not in s
        for ch in [":", "*", "?", "<", ">", "|"]:
            assert ch not in s


class TestEnsureSubpath:
    """Tests for ensure_subpath security function.

    The ensure_subpath function is a critical security utility that validates
    paths stay within a designated root directory. It resolves symbolic links
    and normalizes paths to prevent directory traversal attacks (e.g., ../../../etc/passwd).

    This function is essential for:
    - Preventing unauthorized file access
    - Validating user-provided paths
    - Securing file upload/download operations
    - Protecting against path traversal vulnerabilities
    """

    def test_ensure_subpath_within_root(self, tmp_path: Path):
        """Test that valid subpath stays within root directory.

        Verifies that legitimate child paths are accepted and resolved
        to absolute paths within the root.
        """
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, Path("child"))
        assert str(safe).startswith(str(root.resolve()))

    def test_ensure_subpath_rejects_escape(self, tmp_path: Path):
        """Test that path traversal attempts are rejected.

        This is the core security test - ensures that attempts to escape
        the root directory using ".." are detected and rejected.
        """
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes root"):
            ensure_subpath(root, Path("..") / "outside")

    def test_ensure_subpath_string_input(self, tmp_path: Path):
        """Test ensure_subpath with string input instead of Path."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, "child/nested")
        assert str(safe).startswith(str(root.resolve()))
        assert isinstance(safe, Path)

    def test_ensure_subpath_absolute_path_within_root(self, tmp_path: Path):
        """Test absolute path that is within root."""
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child"
        safe = ensure_subpath(root, child)
        assert str(safe).startswith(str(root.resolve()))
        assert safe == child.resolve()

    def test_ensure_subpath_absolute_path_outside_root(self, tmp_path: Path):
        """Test absolute path outside root raises ValueError."""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        with pytest.raises(ValueError, match="Path escapes root"):
            ensure_subpath(root, outside)

    def test_ensure_subpath_nested_traversal(self, tmp_path: Path):
        """Test nested path traversal attempts.

        Verifies detection of traversal attempts hidden within seemingly
        legitimate paths (e.g., "child/../../outside" escapes via parent refs).
        """
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError, match="Path escapes root"):
            ensure_subpath(root, "child/../../outside")

    def test_ensure_subpath_current_dir(self, tmp_path: Path):
        """Test current directory reference (.) returns root."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, ".")
        assert safe == root.resolve()

    def test_ensure_subpath_empty_string(self, tmp_path: Path):
        """Test empty string returns root directory."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, "")
        assert safe == root.resolve()

    def test_ensure_subpath_deeply_nested(self, tmp_path: Path):
        """Test deeply nested valid path."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, "a/b/c/d/e/f/g/file.txt")
        assert str(safe).startswith(str(root.resolve()))
        assert safe.name == "file.txt"

    def test_ensure_subpath_with_dots_in_name(self, tmp_path: Path):
        """Test path with dots in filename (not traversal)."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, "file.with.dots.txt")
        assert str(safe).startswith(str(root.resolve()))
        assert safe.name == "file.with.dots.txt"

    def test_ensure_subpath_nonexistent_root(self, tmp_path: Path):
        """Test with non-existent root directory."""
        root = tmp_path / "nonexistent"
        # Should not raise - root doesn't need to exist for validation
        safe = ensure_subpath(root, "child")
        assert str(safe).startswith(str(root.resolve()))

    def test_ensure_subpath_both_path_objects(self, tmp_path: Path):
        """Test with both parameters as Path objects."""
        root = tmp_path / "root"
        root.mkdir()
        sub = Path("child") / "nested"
        safe = ensure_subpath(root, sub)
        assert isinstance(safe, Path)
        assert str(safe).startswith(str(root.resolve()))

    def test_ensure_subpath_symlink_within_root(self, tmp_path: Path):
        """Test symlink that stays within root.

        Verifies that symbolic links pointing to locations within the root
        are accepted after resolution. This tests the symlink resolution
        security mechanism.
        """
        root = tmp_path / "root"
        root.mkdir()
        target = root / "target"
        target.mkdir()
        link = root / "link"
        link.symlink_to(target)

        # Resolving the symlink should keep it within root
        safe = ensure_subpath(root, "link")
        assert str(safe).startswith(str(root.resolve()))

    def test_ensure_subpath_symlink_escape_attempt(self, tmp_path: Path):
        """Test symlink that tries to escape root.

        Critical security test: ensures that symbolic links cannot be used
        to bypass directory restrictions by pointing outside the root.
        The function must resolve symlinks before validation.
        """
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = root / "link"
        link.symlink_to(outside)

        # Symlink pointing outside root should be rejected after resolution
        with pytest.raises(ValueError, match="Path escapes root"):
            ensure_subpath(root, "link")

    def test_ensure_subpath_returns_absolute_path(self, tmp_path: Path):
        """Test that returned path is always absolute."""
        root = tmp_path / "root"
        root.mkdir()
        safe = ensure_subpath(root, "child")
        assert safe.is_absolute()


class TestSafeWriteJson:
    """Tests for safe_write_json file writing utility.

    The safe_write_json function provides robust JSON file writing with:
    - Automatic parent directory creation (no need to pre-create dirs)
    - Configurable encoding support (default UTF-8)
    - Customizable indentation for readability
    - Proper error propagation for debugging

    This utility simplifies JSON persistence throughout the application.
    """

    def test_safe_write_json_success(self, tmp_path: Path):
        """Test successful JSON write with nested directory creation."""
        out = tmp_path / "nested" / "file.json"
        payload = {"a": 1, "b": [1, 2, 3]}
        safe_write_json(out, payload)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload

    def test_safe_write_json_raises_oserror(self, monkeypatch, tmp_path: Path):
        """Test that OSError is propagated to caller.

        Verifies that filesystem errors (disk full, I/O errors) are not
        silently caught but properly propagated for error handling.
        """
        out = tmp_path / "boom.json"

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(builtins, "open", boom)
        with pytest.raises(OSError, match="disk full"):
            safe_write_json(out, {"x": 1})

    def test_safe_write_json_custom_encoding(self, tmp_path: Path):
        """Test writing JSON with custom encoding."""
        out = tmp_path / "utf16.json"
        payload = {"unicode": "测试"}
        safe_write_json(out, payload, encoding="utf-16")

        # Read back with same encoding
        data = json.loads(out.read_text(encoding="utf-16"))
        assert data == payload

    def test_safe_write_json_custom_indent(self, tmp_path: Path):
        """Test writing JSON with custom indentation.

        Verifies that the indent parameter controls output formatting,
        useful for creating human-readable configuration or data files.
        """
        out = tmp_path / "indented.json"
        payload = {"a": 1, "b": {"c": 2}}
        safe_write_json(out, payload, indent=4)

        content = out.read_text(encoding="utf-8")
        # Verify 4-space indentation is present
        assert "    " in content  # 4 spaces
        data = json.loads(content)
        assert data == payload

    def test_safe_write_json_no_indent(self, tmp_path: Path):
        """Test writing compact JSON with no indentation."""
        out = tmp_path / "compact.json"
        payload = {"a": 1, "b": 2}
        safe_write_json(out, payload, indent=0)

        content = out.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data == payload

    def test_safe_write_json_complex_structure(self, tmp_path: Path):
        """Test writing complex nested JSON structure."""
        out = tmp_path / "complex.json"
        payload = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"deep": {"deeper": {"value": "found"}}},
        }
        safe_write_json(out, payload)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload
        assert data["nested"]["deep"]["deeper"]["value"] == "found"

    def test_safe_write_json_unicode_content(self, tmp_path: Path):
        """Test writing JSON with unicode characters."""
        out = tmp_path / "unicode.json"
        payload = {
            "english": "hello",
            "chinese": "你好",
            "russian": "привет",
            "emoji": "🚀",
            "mixed": "Hello 世界 🌍",
        }
        safe_write_json(out, payload)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload
        assert data["emoji"] == "🚀"

    def test_safe_write_json_overwrites_existing(self, tmp_path: Path):
        """Test that existing file is completely overwritten.

        Ensures that writing to an existing file replaces the entire content
        rather than appending or merging, preventing data corruption.
        """
        out = tmp_path / "existing.json"

        # Write initial content
        safe_write_json(out, {"old": "data"})
        old_data = json.loads(out.read_text(encoding="utf-8"))
        assert old_data == {"old": "data"}

        # Overwrite with new content - old data should be gone
        safe_write_json(out, {"new": "data"})
        new_data = json.loads(out.read_text(encoding="utf-8"))
        assert new_data == {"new": "data"}
        assert "old" not in new_data

    def test_safe_write_json_creates_deeply_nested_dirs(self, tmp_path: Path):
        """Test creation of deeply nested parent directories."""
        out = tmp_path / "a" / "b" / "c" / "d" / "e" / "file.json"
        payload = {"deep": "nesting"}
        safe_write_json(out, payload)

        assert out.exists()
        assert out.parent.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload

    def test_safe_write_json_empty_dict(self, tmp_path: Path):
        """Test writing empty dictionary."""
        out = tmp_path / "empty.json"
        safe_write_json(out, {})

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == {}

    def test_safe_write_json_empty_list(self, tmp_path: Path):
        """Test writing empty list."""
        out = tmp_path / "empty_list.json"
        safe_write_json(out, [])

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == []

    def test_safe_write_json_list_of_dicts(self, tmp_path: Path):
        """Test writing list of dictionaries."""
        out = tmp_path / "list.json"
        payload = [
            {"id": 1, "name": "first"},
            {"id": 2, "name": "second"},
            {"id": 3, "name": "third"},
        ]
        safe_write_json(out, payload)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload
        assert len(data) == 3

    def test_safe_write_json_special_chars_in_strings(self, tmp_path: Path):
        """Test JSON with special characters in strings."""
        out = tmp_path / "special.json"
        payload = {
            "quotes": 'He said "hello"',
            "newlines": "line1\nline2\nline3",
            "tabs": "col1\tcol2\tcol3",
            "backslash": "path\\to\\file",
            "forward_slash": "path/to/file",
        }
        safe_write_json(out, payload)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload
        assert "\n" in data["newlines"]

    def test_safe_write_json_permission_error(self, monkeypatch, tmp_path: Path):
        """Test that PermissionError is propagated.

        Verifies that permission errors are not silently caught, allowing
        callers to handle access control issues appropriately.
        """
        out = tmp_path / "noperm.json"

        def raise_permission_error(*args, **kwargs):
            raise PermissionError("access denied")

        monkeypatch.setattr(builtins, "open", raise_permission_error)
        with pytest.raises(PermissionError, match="access denied"):
            safe_write_json(out, {"x": 1})

    def test_safe_write_json_parent_exists(self, tmp_path: Path):
        """Test writing when parent directory already exists."""
        parent = tmp_path / "existing"
        parent.mkdir()
        out = parent / "file.json"

        payload = {"test": "data"}
        safe_write_json(out, payload)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload

    def test_safe_write_json_large_data(self, tmp_path: Path):
        """Test writing large JSON data structure.

        Verifies that the function handles larger datasets without issues,
        ensuring scalability for real-world use cases.
        """
        out = tmp_path / "large.json"
        # Create a moderately large nested structure
        payload = {f"key_{i}": {"nested": {"data": [j for j in range(10)]}} for i in range(100)}

        safe_write_json(out, payload)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data == payload
        assert len(data) == 100
