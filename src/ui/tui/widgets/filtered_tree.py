"""Filtered Directory Tree widget for dynamic file filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import DirectoryTree

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class FilteredDirectoryTree(DirectoryTree):
    """A DirectoryTree that supports dynamic filtering of paths."""

    def __init__(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize the filtered directory tree.

        Args:
            path: Root path for the tree
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(path, name=name, id=id, classes=classes)
        self._filter_pattern: str = ""

    @property
    def filter(self) -> str:
        """Get the current filter pattern."""
        return self._filter_pattern

    @filter.setter
    def filter(self, pattern: str) -> None:
        """Set the filter pattern and reload the tree.

        Args:
            pattern: Filter pattern (glob-style or substring)
        """
        if self._filter_pattern != pattern:
            self._filter_pattern = pattern
            # Reload the tree to apply the new filter
            self.reload()

    def _is_glob_pattern(self) -> bool:
        """Check if the current filter is a glob pattern."""
        return "*" in self._filter_pattern or "?" in self._filter_pattern

    def _matches_glob(self, path: Path) -> bool:
        """Check if path matches the glob pattern, with substring fallback."""
        try:
            return path.match(self._filter_pattern)
        except Exception:
            return self._filter_pattern.lower() in path.name.lower()

    def _matches_substring(self, path: Path) -> bool:
        """Check if path name contains the filter pattern (case-insensitive)."""
        return self._filter_pattern.lower() in path.name.lower()

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths based on the current filter pattern.

        Args:
            paths: The paths to filter

        Returns:
            Filtered paths that match the pattern
        """
        if not self._filter_pattern:
            return paths

        matcher = self._matches_glob if self._is_glob_pattern() else self._matches_substring
        return [path for path in paths if matcher(path)]
