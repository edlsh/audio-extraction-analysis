"""Custom themes for the TUI application.

Includes modern palettes inspired by Catppuccin, Gruvbox, and Solarized.
All themes conform to a consistent variable schema for CSS compatibility.
"""

from __future__ import annotations

from textual.theme import Theme

# Animation constants for consistent motion design
ANIM_FAST = 0.15
ANIM_MED = 0.25
ANIM_SLOW = 0.35
ANIM_EASING = "out_cubic"

# Common variable schema that all themes must implement
# This ensures CSS can reference these variables consistently
_common_dark_variables = {
    "text-muted": "#9CA3AF",
    "text-disabled": "#6B7280",
    "card-background": "#1F2937",
    "card-border": "#374151",
    "focus-ring-color": "#0EA5E9",
    "border-subtle": "#374151",
    "success-soft": "#10B981 20%",
    "error-soft": "#EF4444 20%",
    "warning-soft": "#F59E0B 20%",
    "accent-soft": "#0EA5E9 15%",
}

_common_light_variables = {
    "text-muted": "#6B7280",
    "text-disabled": "#9CA3AF",
    "card-background": "#FFFFFF",
    "card-border": "#E5E7EB",
    "focus-ring-color": "#0284C7",
    "border-subtle": "#E5E7EB",
    "success-soft": "#059669 15%",
    "error-soft": "#DC2626 15%",
    "warning-soft": "#D97706 15%",
    "accent-soft": "#0284C7 10%",
}


# =============================================================================
# Original Themes (Updated with extended variables)
# =============================================================================

audio_extraction_blue = Theme(
    name="audio-extraction-blue",
    primary="#0EA5E9",
    secondary="#0284C7",
    warning="#F59E0B",
    error="#EF4444",
    success="#10B981",
    accent="#0EA5E9",
    foreground="#E5E7EB",
    background="#111827",
    surface="#1F2937",
    panel="#374151",
    dark=True,
    variables={
        **_common_dark_variables,
        "footer-key-foreground": "#0EA5E9",
        "button-color-foreground": "#111827",
        "input-selection-background": "#0EA5E9 35%",
        "block-cursor-background": "#0EA5E9",
        "block-cursor-foreground": "#111827",
        "focus-ring-color": "#0EA5E9",
        "accent-soft": "#0EA5E9 15%",
    },
)

audio_extraction_purple = Theme(
    name="audio-extraction-purple",
    primary="#8B5CF6",
    secondary="#7C3AED",
    warning="#F59E0B",
    error="#EF4444",
    success="#10B981",
    accent="#8B5CF6",
    foreground="#E5E7EB",
    background="#111827",
    surface="#1F2937",
    panel="#374151",
    dark=True,
    variables={
        **_common_dark_variables,
        "footer-key-foreground": "#8B5CF6",
        "button-color-foreground": "#111827",
        "input-selection-background": "#8B5CF6 35%",
        "block-cursor-background": "#8B5CF6",
        "block-cursor-foreground": "#111827",
        "focus-ring-color": "#8B5CF6",
        "accent-soft": "#8B5CF6 15%",
    },
)

audio_extraction_green = Theme(
    name="audio-extraction-green",
    primary="#10B981",
    secondary="#059669",
    warning="#F59E0B",
    error="#EF4444",
    success="#10B981",
    accent="#10B981",
    foreground="#E5E7EB",
    background="#111827",
    surface="#1F2937",
    panel="#374151",
    dark=True,
    variables={
        **_common_dark_variables,
        "footer-key-foreground": "#10B981",
        "button-color-foreground": "#111827",
        "input-selection-background": "#10B981 35%",
        "block-cursor-background": "#10B981",
        "block-cursor-foreground": "#111827",
        "focus-ring-color": "#10B981",
        "accent-soft": "#10B981 15%",
    },
)

audio_extraction_light_blue = Theme(
    name="audio-extraction-light",
    primary="#0284C7",
    secondary="#0EA5E9",
    warning="#F59E0B",
    error="#DC2626",
    success="#059669",
    accent="#0EA5E9",
    foreground="#1F2937",
    background="#F9FAFB",
    surface="#F3F4F6",
    panel="#E5E7EB",
    dark=False,
    variables={
        **_common_light_variables,
        "footer-key-foreground": "#0EA5E9",
        "button-color-foreground": "#F9FAFB",
        "input-selection-background": "#0EA5E9 25%",
        "block-cursor-background": "#0EA5E9",
        "block-cursor-foreground": "#F9FAFB",
        "focus-ring-color": "#0EA5E9",
        "accent-soft": "#0EA5E9 10%",
    },
)


# =============================================================================
# Catppuccin Themes
# =============================================================================

catppuccin_mocha = Theme(
    name="catppuccin-mocha",
    primary="#CBA6F7",  # Mauve
    secondary="#B4BEFE",  # Lavender
    warning="#F9E2AF",  # Yellow
    error="#F38BA8",  # Red
    success="#A6E3A1",  # Green
    accent="#CBA6F7",  # Mauve
    foreground="#CDD6F4",  # Text
    background="#1E1E2E",  # Base
    surface="#313244",  # Surface0
    panel="#45475A",  # Surface1
    dark=True,
    variables={
        "text-muted": "#A6ADC8",  # Subtext0
        "text-disabled": "#6C7086",  # Overlay0
        "card-background": "#313244",  # Surface0
        "card-border": "#45475A",  # Surface1
        "focus-ring-color": "#CBA6F7",
        "border-subtle": "#45475A",
        "success-soft": "#A6E3A1 20%",
        "error-soft": "#F38BA8 20%",
        "warning-soft": "#F9E2AF 20%",
        "accent-soft": "#CBA6F7 15%",
        "footer-key-foreground": "#CBA6F7",
        "button-color-foreground": "#1E1E2E",
        "input-selection-background": "#CBA6F7 35%",
        "block-cursor-background": "#CBA6F7",
        "block-cursor-foreground": "#1E1E2E",
    },
)

catppuccin_macchiato = Theme(
    name="catppuccin-macchiato",
    primary="#C6A0F6",  # Mauve
    secondary="#B7BDF8",  # Lavender
    warning="#EED49F",  # Yellow
    error="#ED8796",  # Red
    success="#A6DA95",  # Green
    accent="#C6A0F6",  # Mauve
    foreground="#CAD3F5",  # Text
    background="#24273A",  # Base
    surface="#363A4F",  # Surface0
    panel="#494D64",  # Surface1
    dark=True,
    variables={
        "text-muted": "#A5ADCB",  # Subtext0
        "text-disabled": "#6E738D",  # Overlay0
        "card-background": "#363A4F",
        "card-border": "#494D64",
        "focus-ring-color": "#C6A0F6",
        "border-subtle": "#494D64",
        "success-soft": "#A6DA95 20%",
        "error-soft": "#ED8796 20%",
        "warning-soft": "#EED49F 20%",
        "accent-soft": "#C6A0F6 15%",
        "footer-key-foreground": "#C6A0F6",
        "button-color-foreground": "#24273A",
        "input-selection-background": "#C6A0F6 35%",
        "block-cursor-background": "#C6A0F6",
        "block-cursor-foreground": "#24273A",
    },
)

catppuccin_latte = Theme(
    name="catppuccin-latte",
    primary="#8839EF",  # Mauve
    secondary="#7287FD",  # Lavender
    warning="#DF8E1D",  # Yellow
    error="#D20F39",  # Red
    success="#40A02B",  # Green
    accent="#8839EF",  # Mauve
    foreground="#4C4F69",  # Text
    background="#EFF1F5",  # Base
    surface="#E6E9EF",  # Surface0
    panel="#DCE0E8",  # Surface1
    dark=False,
    variables={
        "text-muted": "#6C6F85",  # Subtext0
        "text-disabled": "#9CA0B0",  # Overlay0
        "card-background": "#E6E9EF",
        "card-border": "#DCE0E8",
        "focus-ring-color": "#8839EF",
        "border-subtle": "#DCE0E8",
        "success-soft": "#40A02B 15%",
        "error-soft": "#D20F39 15%",
        "warning-soft": "#DF8E1D 15%",
        "accent-soft": "#8839EF 10%",
        "footer-key-foreground": "#8839EF",
        "button-color-foreground": "#EFF1F5",
        "input-selection-background": "#8839EF 25%",
        "block-cursor-background": "#8839EF",
        "block-cursor-foreground": "#EFF1F5",
    },
)


# =============================================================================
# Gruvbox Themes
# =============================================================================

gruvbox_dark = Theme(
    name="gruvbox-dark",
    primary="#D79921",  # Yellow
    secondary="#458588",  # Blue
    warning="#FE8019",  # Orange
    error="#CC241D",  # Red
    success="#98971A",  # Green
    accent="#D79921",  # Yellow
    foreground="#EBDBB2",  # fg
    background="#282828",  # bg
    surface="#3C3836",  # bg1
    panel="#504945",  # bg2
    dark=True,
    variables={
        "text-muted": "#A89984",  # gray
        "text-disabled": "#928374",  # gray darker
        "card-background": "#3C3836",
        "card-border": "#504945",
        "focus-ring-color": "#D79921",
        "border-subtle": "#504945",
        "success-soft": "#98971A 20%",
        "error-soft": "#CC241D 20%",
        "warning-soft": "#FE8019 20%",
        "accent-soft": "#D79921 15%",
        "footer-key-foreground": "#D79921",
        "button-color-foreground": "#282828",
        "input-selection-background": "#D79921 35%",
        "block-cursor-background": "#D79921",
        "block-cursor-foreground": "#282828",
    },
)

gruvbox_light = Theme(
    name="gruvbox-light",
    primary="#B57614",  # Yellow dark
    secondary="#076678",  # Blue dark
    warning="#AF3A03",  # Orange dark
    error="#9D0006",  # Red dark
    success="#79740E",  # Green dark
    accent="#B57614",  # Yellow dark
    foreground="#3C3836",  # fg
    background="#FBF1C7",  # bg
    surface="#EBDBB2",  # bg1
    panel="#D5C4A1",  # bg2
    dark=False,
    variables={
        "text-muted": "#7C6F64",  # gray dark
        "text-disabled": "#928374",  # gray
        "card-background": "#EBDBB2",
        "card-border": "#D5C4A1",
        "focus-ring-color": "#B57614",
        "border-subtle": "#D5C4A1",
        "success-soft": "#79740E 15%",
        "error-soft": "#9D0006 15%",
        "warning-soft": "#AF3A03 15%",
        "accent-soft": "#B57614 10%",
        "footer-key-foreground": "#B57614",
        "button-color-foreground": "#FBF1C7",
        "input-selection-background": "#B57614 25%",
        "block-cursor-background": "#B57614",
        "block-cursor-foreground": "#FBF1C7",
    },
)


# =============================================================================
# Solarized Themes
# =============================================================================

solarized_dark = Theme(
    name="solarized-dark",
    primary="#268BD2",  # Blue
    secondary="#2AA198",  # Cyan
    warning="#B58900",  # Yellow
    error="#DC322F",  # Red
    success="#859900",  # Green
    accent="#268BD2",  # Blue
    foreground="#839496",  # base0
    background="#002B36",  # base03
    surface="#073642",  # base02
    panel="#073642",  # base02
    dark=True,
    variables={
        "text-muted": "#657B83",  # base00
        "text-disabled": "#586E75",  # base01
        "card-background": "#073642",
        "card-border": "#586E75",
        "focus-ring-color": "#268BD2",
        "border-subtle": "#586E75",
        "success-soft": "#859900 20%",
        "error-soft": "#DC322F 20%",
        "warning-soft": "#B58900 20%",
        "accent-soft": "#268BD2 15%",
        "footer-key-foreground": "#268BD2",
        "button-color-foreground": "#002B36",
        "input-selection-background": "#268BD2 35%",
        "block-cursor-background": "#268BD2",
        "block-cursor-foreground": "#002B36",
    },
)

solarized_light = Theme(
    name="solarized-light",
    primary="#268BD2",  # Blue
    secondary="#2AA198",  # Cyan
    warning="#B58900",  # Yellow
    error="#DC322F",  # Red
    success="#859900",  # Green
    accent="#268BD2",  # Blue
    foreground="#657B83",  # base00
    background="#FDF6E3",  # base3
    surface="#EEE8D5",  # base2
    panel="#EEE8D5",  # base2
    dark=False,
    variables={
        "text-muted": "#839496",  # base0
        "text-disabled": "#93A1A1",  # base1
        "card-background": "#EEE8D5",
        "card-border": "#93A1A1",
        "focus-ring-color": "#268BD2",
        "border-subtle": "#93A1A1",
        "success-soft": "#859900 15%",
        "error-soft": "#DC322F 15%",
        "warning-soft": "#B58900 15%",
        "accent-soft": "#268BD2 10%",
        "footer-key-foreground": "#268BD2",
        "button-color-foreground": "#FDF6E3",
        "input-selection-background": "#268BD2 25%",
        "block-cursor-background": "#268BD2",
        "block-cursor-foreground": "#FDF6E3",
    },
)


# =============================================================================
# Theme Registry
# =============================================================================

CUSTOM_THEMES = [
    # Original themes
    audio_extraction_blue,
    audio_extraction_purple,
    audio_extraction_green,
    audio_extraction_light_blue,
    # Catppuccin
    catppuccin_mocha,
    catppuccin_macchiato,
    catppuccin_latte,
    # Gruvbox
    gruvbox_dark,
    gruvbox_light,
    # Solarized
    solarized_dark,
    solarized_light,
]

DEFAULT_CUSTOM_THEME = "audio-extraction-blue"

# Theme categories for UI organization
THEME_CATEGORIES = {
    "Audio Extraction": [
        "audio-extraction-blue",
        "audio-extraction-purple",
        "audio-extraction-green",
        "audio-extraction-light",
    ],
    "Catppuccin": [
        "catppuccin-mocha",
        "catppuccin-macchiato",
        "catppuccin-latte",
    ],
    "Gruvbox": [
        "gruvbox-dark",
        "gruvbox-light",
    ],
    "Solarized": [
        "solarized-dark",
        "solarized-light",
    ],
}
