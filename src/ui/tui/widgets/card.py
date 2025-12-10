"""Base Card widget for consistent card-style containers.

Provides a reusable card component with:
- Rounded borders
- Consistent padding and spacing
- Status variant support (primary, success, error, warning, muted)
- Theme-aware styling via CSS variables
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from ..themes import ANIM_EASING, ANIM_FAST, ANIM_MED


class Card(Static):
    """A card container with rounded borders and consistent styling.

    Use this as a base class for custom cards or directly for simple containers.

    CSS Classes:
        .card--primary: Primary accent styling
        .card--success: Success state styling
        .card--error: Error state styling
        .card--warning: Warning state styling
        .card--muted: Subdued/disabled styling

    Example:
        ```python
        yield Card(
            Label("Card Title", classes="card-title"),
            Label("Card content here"),
            classes="card--primary",
        )
        ```
    """

    DEFAULT_CSS = """
    Card {
        width: 100%;
        height: auto;
        padding: 1 2;
        margin: 1 0;
        border: round $panel;
        background: $surface;
    }

    Card:focus-within {
        border: round $accent;
    }

    /* Card title styling */
    Card .card-title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    Card .card-subtitle {
        color: $text-disabled;
        padding: 0 0 1 0;
    }

    Card .card-body {
        color: $foreground;
    }

    Card .card-footer {
        color: $text-disabled;
        padding: 1 0 0 0;
        border-top: solid $panel;
        margin-top: 1;
    }

    /* Status variants */
    Card.card--primary {
        border: round $accent;
    }

    Card.card--success {
        border: round $success;
    }

    Card.card--error {
        border: round $error;
    }

    Card.card--warning {
        border: round $warning;
    }

    Card.card--muted {
        border: round $panel;
        background: $surface;
    }

    /* Compact variant */
    Card.card--compact {
        padding: 0 1;
        margin: 0 0 1 0;
    }

    /* Elevated variant with visual hierarchy */
    Card.card--elevated {
        background: $panel;
    }
    """

    variant: reactive[str] = reactive("")

    def __init__(
        self,
        *children: Widget,
        variant: str = "",
        title: str | None = None,
        subtitle: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Card.

        Args:
            *children: Child widgets to render inside the card.
            variant: Card variant (primary, success, error, warning, muted).
            title: Optional card title text.
            subtitle: Optional card subtitle text.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(*children, **kwargs)
        self._title = title
        self._subtitle = subtitle
        if variant:
            self.variant = variant

    def compose(self) -> ComposeResult:
        """Compose the card layout."""
        if self._title:
            yield Label(self._title, classes="card-title")
        if self._subtitle:
            yield Label(self._subtitle, classes="card-subtitle")

    def watch_variant(self, variant: str) -> None:
        """React to variant changes."""
        self.remove_class(
            "card--primary",
            "card--success",
            "card--error",
            "card--warning",
            "card--muted",
        )
        if variant:
            self.add_class(f"card--{variant}")

    def set_variant(self, variant: str) -> None:
        """Set the card variant with optional animation.

        Args:
            variant: New variant (primary, success, error, warning, muted, or empty).
        """
        self.variant = variant


class HeroCard(Card):
    """A larger, centered card for hero sections like welcome screens.

    Features:
    - Centered content
    - Larger max-width
    - Optional gradient background
    """

    DEFAULT_CSS = """
    HeroCard {
        width: 80%;
        max-width: 90;
        padding: 2 4;
        margin: 2 auto;
        border: round $panel;
        background: $surface;
        align: center middle;
        content-align: center middle;
    }

    HeroCard .card-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1 0;
    }

    HeroCard .card-subtitle {
        text-align: center;
        color: $text-disabled;
        padding: 0 0 1 0;
    }

    HeroCard .card-body {
        text-align: center;
    }
    """


class InfoCard(Card):
    """A card with an icon and structured info layout.

    Useful for displaying status information, stats, or feature highlights.
    """

    DEFAULT_CSS = """
    InfoCard {
        width: 100%;
        height: auto;
        padding: 1 2;
        margin: 0 0 1 0;
        border: round $panel;
        background: $surface;
    }

    InfoCard .info-icon {
        width: 3;
        text-align: center;
        color: $accent;
    }

    InfoCard .info-content {
        padding-left: 1;
    }

    InfoCard .info-label {
        color: $text-disabled;
    }

    InfoCard .info-value {
        text-style: bold;
        color: $foreground;
    }
    """

    def __init__(
        self,
        icon: str = "•",
        label: str = "",
        value: str = "",
        **kwargs,
    ) -> None:
        """Initialize an InfoCard.

        Args:
            icon: Icon character or emoji to display.
            label: Label text (muted).
            value: Value text (bold).
            **kwargs: Additional arguments passed to Card.
        """
        super().__init__(**kwargs)
        self._icon = icon
        self._label = label
        self._value = value

    def compose(self) -> ComposeResult:
        """Compose the info card layout."""
        yield Label(self._icon, classes="info-icon")
        with Vertical(classes="info-content"):
            yield Label(self._label, classes="info-label")
            yield Label(self._value, classes="info-value")
