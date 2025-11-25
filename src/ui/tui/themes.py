"""Custom themes for the TUI application."""

from __future__ import annotations

from textual.theme import Theme

# Custom theme with blue accent instead of orange
audio_extraction_blue = Theme(
    name="audio-extraction-blue",
    primary="#0EA5E9",  # Sky blue (was #0178D4)
    secondary="#0284C7",  # Darker sky blue (was #004578)
    warning="#F59E0B",  # Amber for warnings (was #ffa62b)
    error="#EF4444",  # Red for errors (was #ba3c5b)
    success="#10B981",  # Green for success (was #4EBF71)
    accent="#0EA5E9",  # Sky blue accent (was orange #ffa62b)
    foreground="#E5E7EB",  # Light gray text
    background="#111827",  # Dark background
    surface="#1F2937",  # Slightly lighter surface
    panel="#374151",  # Panel background
    dark=True,
    variables={
        "footer-key-foreground": "#0EA5E9",
        "button-color-foreground": "#111827",
        "input-selection-background": "#0EA5E9 35%",
        "block-cursor-background": "#0EA5E9",
        "block-cursor-foreground": "#111827",
    },
)

# Alternative theme with purple accent
audio_extraction_purple = Theme(
    name="audio-extraction-purple",
    primary="#8B5CF6",  # Purple
    secondary="#7C3AED",  # Darker purple
    warning="#F59E0B",  # Amber for warnings
    error="#EF4444",  # Red for errors
    success="#10B981",  # Green for success
    accent="#8B5CF6",  # Purple accent (was orange #ffa62b)
    foreground="#E5E7EB",  # Light gray text
    background="#111827",  # Dark background
    surface="#1F2937",  # Slightly lighter surface
    panel="#374151",  # Panel background
    dark=True,
    variables={
        "footer-key-foreground": "#8B5CF6",
        "button-color-foreground": "#111827",
        "input-selection-background": "#8B5CF6 35%",
        "block-cursor-background": "#8B5CF6",
        "block-cursor-foreground": "#111827",
    },
)

# Alternative theme with green accent
audio_extraction_green = Theme(
    name="audio-extraction-green",
    primary="#10B981",  # Green
    secondary="#059669",  # Darker green
    warning="#F59E0B",  # Amber for warnings
    error="#EF4444",  # Red for errors
    success="#10B981",  # Green for success
    accent="#10B981",  # Green accent (was orange #ffa62b)
    foreground="#E5E7EB",  # Light gray text
    background="#111827",  # Dark background
    surface="#1F2937",  # Slightly lighter surface
    panel="#374151",  # Panel background
    dark=True,
    variables={
        "footer-key-foreground": "#10B981",
        "button-color-foreground": "#111827",
        "input-selection-background": "#10B981 35%",
        "block-cursor-background": "#10B981",
        "block-cursor-foreground": "#111827",
    },
)

# Light theme with blue accent
audio_extraction_light_blue = Theme(
    name="audio-extraction-light",
    primary="#0284C7",  # Sky blue
    secondary="#0EA5E9",  # Lighter sky blue
    warning="#F59E0B",  # Amber for warnings
    error="#DC2626",  # Red for errors
    success="#059669",  # Green for success
    accent="#0EA5E9",  # Sky blue accent (was orange #ffa62b)
    foreground="#1F2937",  # Dark text on light background
    background="#F9FAFB",  # Light background
    surface="#F3F4F6",  # Slightly darker surface
    panel="#E5E7EB",  # Panel background
    dark=False,
    variables={
        "footer-key-foreground": "#0EA5E9",
        "button-color-foreground": "#F9FAFB",
        "input-selection-background": "#0EA5E9 25%",
        "block-cursor-background": "#0EA5E9",
        "block-cursor-foreground": "#F9FAFB",
    },
)

# List of all custom themes for easy registration
CUSTOM_THEMES = [
    audio_extraction_blue,
    audio_extraction_purple,
    audio_extraction_green,
    audio_extraction_light_blue,
]

# Default custom theme
DEFAULT_CUSTOM_THEME = "audio-extraction-blue"
