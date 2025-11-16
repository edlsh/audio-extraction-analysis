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

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths based on the current filter pattern.

        Args:
            paths: The paths to filter

        Returns:
            Filtered paths that match the pattern
        """
        if not self._filter_pattern:
            # No filter, return all paths
            return paths

        # Convert pattern to lowercase for case-insensitive matching
        pattern_lower = self._filter_pattern.lower()

        # Support both glob patterns and simple substring matching
        filtered_paths = []
        for path in paths:
            path_str_lower = path.name.lower()

            # Check for glob pattern
            if "*" in self._filter_pattern or "?" in self._filter_pattern:
                # Use glob-style matching
                try:
                    if path.match(self._filter_pattern):
                        filtered_paths.append(path)
                except Exception:
                    # Fallback to substring matching if glob fails
                    if pattern_lower in path_str_lower:
                        filtered_paths.append(path)
            else:
                # Simple substring matching (case-insensitive)
                if pattern_lower in path_str_lower:
                    filtered_paths.append(path)

        return filtered_paths
