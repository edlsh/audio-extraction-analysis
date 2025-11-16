"""Theme selection screen for the TUI application."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual._context import active_app
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

from ..persistence import save_settings
from ..themes import CUSTOM_THEMES

if TYPE_CHECKING:
    from ..app import AudioExtractionApp


class ThemeSelectorScreen(Screen):
    """Screen for selecting application theme."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "select", "Select", show=False),
    ]

    CSS = """
    ThemeSelectorScreen {
        align: center middle;
    }

    #theme-container {
        width: 60;
        height: 80%;
        min-height: 20;
        max-height: 40;
        border: solid $accent;
        padding: 1;
    }

    #theme-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    OptionList {
        height: 1fr;
        border: none;
        padding: 0 1;
    }

    OptionList:focus {
        border: none;
    }

    #current-theme {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }
    """

    def __init__(self):
        """Initialize the theme selector screen."""
        super().__init__()
        self._app_override: AudioExtractionApp | None = None

    @property
    def app(self) -> AudioExtractionApp:
        """Get the app instance."""
        if self._app_override is not None:
            return self._app_override
        return cast("AudioExtractionApp", super().app)

    @app.setter
    def app(self, value: AudioExtractionApp) -> None:
        """Set the app instance for testing."""
        self._app_override = value
        active_app.set(value)

    def compose(self) -> ComposeResult:
        """Compose the theme selector layout."""
        yield Header()

        with Container(id="theme-container"):
            yield Label("Select Theme", id="theme-title")
            yield OptionList(id="theme-list")
            yield Static("", id="current-theme")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the theme list when screen is mounted."""
        option_list = self.query_one("#theme-list", OptionList)
        current_theme = self.app.theme

        # Add custom themes section
        custom_theme_names = [theme.name for theme in CUSTOM_THEMES]
        if custom_theme_names:
            # Add a disabled option as a separator
            option_list.add_option(Option("──── Custom Themes ────", disabled=True))
            for theme_name in custom_theme_names:
                display_name = self._format_theme_name(theme_name)
                if theme_name == current_theme:
                    display_name = f"▶ {display_name}"
                option_list.add_option(Option(display_name, id=theme_name))

        # Add built-in dark themes
        dark_themes = [
            "nord",
            "gruvbox",
            "dracula",
            "monokai",
            "catppuccin-mocha",
            "tokyo-night",
            "textual-dark",
        ]
        available_dark = [t for t in dark_themes if t in self.app.available_themes]
        if available_dark:
            # Add a disabled option as a separator
            option_list.add_option(Option("──── Built-in Dark Themes ────", disabled=True))
            for theme_name in available_dark:
                display_name = self._format_theme_name(theme_name)
                if theme_name == current_theme:
                    display_name = f"▶ {display_name}"
                option_list.add_option(Option(display_name, id=theme_name))

        # Add built-in light themes
        light_themes = [
            "textual-light",
            "catppuccin-latte",
            "solarized-light",
        ]
        available_light = [t for t in light_themes if t in self.app.available_themes]
        if available_light:
            # Add a disabled option as a separator
            option_list.add_option(Option("──── Built-in Light Themes ────", disabled=True))
            for theme_name in available_light:
                display_name = self._format_theme_name(theme_name)
                if theme_name == current_theme:
                    display_name = f"▶ {display_name}"
                option_list.add_option(Option(display_name, id=theme_name))

        # Update current theme display
        self._update_current_theme_display()

        # Focus on the option list
        option_list.focus()

        # Try to highlight the current theme
        self._highlight_current_theme()

    def _format_theme_name(self, theme_name: str) -> str:
        """Format theme name for display.

        Args:
            theme_name: Internal theme name

        Returns:
            Formatted display name
        """
        # Remove prefixes
        name = theme_name.replace("audio-extraction-", "")
        name = name.replace("textual-", "")
        name = name.replace("-", " ")

        # Capitalize words
        words = name.split()
        formatted = " ".join(word.capitalize() for word in words)

        # Add emoji indicators for our custom themes
        if theme_name.startswith("audio-extraction"):
            if "blue" in theme_name:
                formatted = f"🔵 {formatted}"
            elif "purple" in theme_name:
                formatted = f"🟣 {formatted}"
            elif "green" in theme_name:
                formatted = f"🟢 {formatted}"
            elif "light" in theme_name:
                formatted = f"☀️ {formatted}"

        return formatted

    def _update_current_theme_display(self) -> None:
        """Update the current theme display text."""
        current_theme_label = self.query_one("#current-theme", Static)
        current_theme = self.app.theme
        formatted_name = self._format_theme_name(current_theme)
        current_theme_label.update(f"Current: {formatted_name}")

    def _highlight_current_theme(self) -> None:
        """Highlight the current theme in the list."""
        option_list = self.query_one("#theme-list", OptionList)
        current_theme = self.app.theme

        # Find and highlight the current theme option
        for index in range(option_list.option_count):
            option = option_list.get_option_at_index(index)
            if option and hasattr(option, "id") and option.id == current_theme:
                option_list.highlighted = index
                break

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle theme selection.

        Args:
            event: Option selected event
        """
        if event.option_id:
            self._apply_theme(event.option_id)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the selected theme.

        Args:
            theme_name: Name of the theme to apply
        """
        # Apply the theme
        self.app.theme = theme_name

        # Save to settings
        self.app.settings["ui"]["theme"] = theme_name
        save_settings(self.app.settings)

        # Show notification
        formatted_name = self._format_theme_name(theme_name)
        self.app.notify(f"Theme changed to: {formatted_name}", severity="information")

        # Return to previous screen
        self.app.pop_screen()

    def action_cancel(self) -> None:
        """Cancel theme selection and return to previous screen."""
        self.app.pop_screen()

    def action_select(self) -> None:
        """Select the highlighted theme."""
        option_list = self.query_one("#theme-list", OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option and hasattr(option, "id") and option.id:
                self._apply_theme(option.id)
